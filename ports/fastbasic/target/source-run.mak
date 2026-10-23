# Exec816 source engines: all parser/runtime objects share one token table.
SOURCE_AS_SRC=$(COMPILER_AS_SRC) src/source-run.asm
build/bin/fbrun.xex: $(SOURCE_AS_SRC:src/%.asm=build/obj/fp/%.o) $(A800_FP_OBJS) | build/bin $(LD65_HOST)
	$(LD65_HOST) $(LD65_FLAGS) -Ln $(@:.xex=.lbl) -m $(@:.xex=.map) -o $@ $^
build/bin/fbirun.xex: $(SOURCE_AS_SRC:src/%.asm=build/obj/int/%.o) $(A800_OBJS) | build/bin $(LD65_HOST)
	$(LD65_HOST) $(LD65_FLAGS) -Ln $(@:.xex=.lbl) -m $(@:.xex=.map) -o $@ $^
