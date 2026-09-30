// Thin host-only adapter to the independently maintained Altirra SDFS library.
// Build against the pinned Altirra source/libraries; no Exec816 parser is used.
#include <at/atio/diskimage.h>
#include <at/atio/diskfs.h>
#include <vd2/system/date.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <vector>
#include <algorithm>

namespace fs = std::filesystem;

// The portable system archive references these UI hooks. This command-line
// filesystem adapter never opens or saves the emulator's settings registry.
void ATUILoadRegistry(const wchar_t*) {}
void ATUISaveRegistry(const wchar_t*) {}

static void import_tree(IATDiskFS& disk, ATDiskFSKey parent, const fs::path& path) {
    std::vector<fs::path> entries;
    for (auto& entry : fs::directory_iterator(path)) entries.push_back(entry.path());
    std::sort(entries.begin(), entries.end());
    for (auto& entry : entries) {
        auto name = entry.filename().string();
        ATDiskFSKey key;
        if (fs::is_directory(entry)) {
            key = disk.CreateDir(parent, name.c_str());
            import_tree(disk, key, entry);
        } else {
            std::ifstream in(entry, std::ios::binary);
            std::vector<char> bytes((std::istreambuf_iterator<char>(in)), {});
            key = disk.WriteFile(parent, name.c_str(), bytes.data(), bytes.size());
        }
        VDExpandedDate date{};
        date.mYear = 2026; date.mMonth = 9; date.mDay = 25;
        disk.SetFileTimestamp(key, date);
    }
}

static void export_tree(IATDiskFS& disk, ATDiskFSKey parent, const fs::path& path) {
    fs::create_directories(path);
    ATDiskFSEntryInfo info;
    auto scan = disk.FindFirst(parent, info);
    if (scan == ATDiskFSFindHandle::Invalid) return;
    do {
        auto target = path / info.mFileName.c_str();
        if (info.mbIsDirectory) export_tree(disk, info.mKey, target);
        else {
            vdfastvector<uint8> bytes;
            disk.ReadFile(info.mKey, bytes);
            std::ofstream out(target, std::ios::binary);
            out.write(reinterpret_cast<const char*>(bytes.data()), bytes.size());
            if (!out) throw std::runtime_error("Cannot write exported file");
        }
    } while (disk.FindNext(scan, info));
    disk.FindEnd(scan);
}

int main(int argc, char **argv) {
    try {
        if (argc != 4 && argc != 6) throw std::runtime_error("make IMAGE DIRECTORY SECTORS BYTES | extract IMAGE DIRECTORY");
        const bool make = std::string(argv[1]) == "make";
        if (make != (argc == 6) || (!make && std::string(argv[1]) != "extract"))
            throw std::runtime_error("Invalid operation");
        vdrefptr<IATDiskImage> image;
        auto image_path = fs::path(argv[2]).wstring();
        if (make) ATCreateDiskImage(std::stoul(argv[4]), 3, std::stoul(argv[5]), ~image);
        else ATLoadDiskImage(image_path.c_str(), ~image);
        std::unique_ptr<IATDiskFS> disk(make ? ATDiskFormatImageSDX2(image, "EXEC816") : ATDiskMountImageSDX2(image, true));
        if (make) {
            import_tree(*disk, ATDiskFSKey::None, argv[3]);
            disk->Flush();
            // The producer normally seeds these two identity bytes from host
            // time. Fix them for reproducible data-disk bundles.
            uint8 boot[128];
            image->ReadVirtualSector(0, boot, 128);
            boot[38] = 1; boot[39] = 0x81;
            image->WriteVirtualSector(0, boot, 128);
            image->Save(image_path.c_str(), kATDiskImageFormat_ATR);
        } else export_tree(*disk, ATDiskFSKey::None, argv[3]);
        ATDiskFSValidationReport report;
        if (!disk->Validate(report)) throw std::runtime_error("Independent SDFS validation failed");
        return 0;
    } catch (const MyError& error) {
        std::cerr << error.c_str() << '\n';
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
    }
    return 1;
}
