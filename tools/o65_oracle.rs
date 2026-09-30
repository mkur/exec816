//! Test-only adapter to the pinned compiler's reference inspector/relocator.
use actionc::mir65816::o65;
use serde_json::{Value, json};
use std::io::{self, Read};

fn main() {
    let mut input = String::new();
    io::stdin().read_to_string(&mut input).unwrap();
    let request: Value = serde_json::from_str(&input).unwrap();
    let bytes = std::fs::read(request["file"].as_str().unwrap()).unwrap();
    let mut result = json!({"valid": o65::compact::inspect(&bytes).is_ok()});
    if request["prefixes"] == true {
        result["accepted_prefixes"] = json!((0..bytes.len())
            .filter(|n| o65::compact::inspect(&bytes[..*n]).is_ok()).collect::<Vec<_>>());
    }
    if let Some(mutations) = request["mutations"].as_array() {
        let accepted = mutations.iter().enumerate().filter_map(|(i, m)| {
            let mut altered = bytes.clone();
            altered[m[0].as_u64().unwrap() as usize] = m[1].as_u64().unwrap() as u8;
            o65::compact::inspect(&altered).is_ok().then_some(i)
        }).collect::<Vec<_>>();
        result["accepted_mutations"] = json!(accepted);
    }
    if !request["placement"].is_null() {
        let placement = serde_json::from_value(request["placement"].clone()).unwrap();
        match o65::compact::relocate(&bytes, &placement) {
            Ok(image) => {
                result["segments"] = serde_json::to_value(&image.segments).unwrap();
                result["zero_fill"] = serde_json::to_value(&image.zero_fill).unwrap();
                result["entry"] = json!(image.entry);
            }
            Err(error) => result["error"] = json!(error),
        }
    }
    println!("{result}");
}
