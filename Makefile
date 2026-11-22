# EGM kit: `make`, `make test`, `make install` (PREFIX=/usr/local by default; PREFIX=~/.local needs no sudo)
# Python users: `pip install .` instead (compiles the engine into the package and installs `egm`).
PREFIX ?= /usr/local
CXX ?= c++
CXXFLAGS ?= -O2 -std=c++17 -Wall
PY ?= python3
BIN = build/voltex2

.PHONY: all test repro sanitize interop install uninstall clean

all: $(BIN)

$(BIN): src/voltex2.cpp
	@mkdir -p build
	$(CXX) $(CXXFLAGS) -o $@ $<

test: $(BIN)
	@$(PY) -I tests/run_tests.py --egm bin/egm
	@$(PY) -m unittest tests/test_sdk.py tests/test_mcp.py tests/test_mimic.py

repro: $(BIN)
	@$(PY) -I tests/run_tests.py --egm bin/egm --only repro

sanitize: src/voltex2.cpp
	@mkdir -p build
	$(CXX) -O1 -g -std=c++17 -fsanitize=address,undefined -fno-omit-frame-pointer -o build/voltex2-asan $<
	@ASAN_OPTIONS=detect_leaks=0:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 \
	  VOLTEX=build/voltex2-asan $(PY) -I tests/run_tests.py --egm bin/egm --only engine,cli,repro
	@ASAN_OPTIONS=detect_leaks=0:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1 VOLTEX=build/voltex2-asan $(PY) -m unittest tests/test_sdk.py tests/test_mcp.py
	@echo "(memory errors and undefined behaviour are fatal here; exit-time leaks are known: the grammar has no destructor)"

# Drive `egm mcp` with the official MCP Python client (makes build/mcp-venv; needs network once)
interop: $(BIN)
	@test -x build/mcp-venv/bin/python || ($(PY) -m venv build/mcp-venv && build/mcp-venv/bin/pip install -q mcp)
	@build/mcp-venv/bin/python tests/interop_mcp_client.py bin/egm examples/tokenomics/M.txt 2>/dev/null

install: $(BIN)
	install -d $(DESTDIR)$(PREFIX)/bin $(DESTDIR)$(PREFIX)/share/egm/egm $(DESTDIR)$(PREFIX)/share/egm/examples
	install -m 755 $(BIN) $(DESTDIR)$(PREFIX)/bin/voltex2
	install -m 755 bin/egm $(DESTDIR)$(PREFIX)/bin/egm
	install -m 644 egm/*.py $(DESTDIR)$(PREFIX)/share/egm/egm/
	cp -R examples/. $(DESTDIR)$(PREFIX)/share/egm/examples/
	@echo "installed: $(PREFIX)/bin/egm, $(PREFIX)/bin/voltex2, examples in $(PREFIX)/share/egm/examples"

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/egm $(DESTDIR)$(PREFIX)/bin/voltex2
	rm -rf $(DESTDIR)$(PREFIX)/share/egm

clean:
	rm -rf build
