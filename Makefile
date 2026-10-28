# Copyright (C) 2026 Pelle van der Heide
# SPDX-License-Identifier: GPL-2.0-or-later

PREFIX     ?= /usr
CUPSFILTER ?= $(PREFIX)/lib/cups/filter
DATADIR    ?= $(PREFIX)/share/foo2qpdl
CC         ?= cc
CFLAGS     ?= -O2 -Wall -Wextra
PYTHON     ?= python3
WRAPPER_SRC ?= $(shell command -v foo2qpdl-wrapper)

all: c410scms-filter

c410scms-filter: src/c410scms-filter.c
	$(CC) $(CFLAGS) -o $@ $<

# make data CTS=/path/to/C410sc.cts [LIB=/path/to/libscmssc.so]
c410scms.dat:
	@test -n "$(CTS)" || { echo "set CTS=/path/to/C410sc.cts (from Samsung's driver, see README)"; exit 1; }
	$(PYTHON) tools/c410scms-gen $(CTS) $(LIB) -o $@
data: c410scms.dat

foo2qpdl-c410scms-wrapper:
	@test -n "$(WRAPPER_SRC)" || { echo "foo2qpdl-wrapper not found; install foo2zjs (printer-driver-foo2zjs)"; exit 1; }
	$(PYTHON) tools/patch-foo2qpdl-wrapper $(WRAPPER_SRC) $@
	chmod +x $@

install: c410scms-filter c410scms.dat foo2qpdl-c410scms-wrapper
	install -D -m 755 c410scms-filter $(DESTDIR)$(CUPSFILTER)/c410scms-filter
	install -D -m 755 foo2qpdl-c410scms-wrapper $(DESTDIR)$(CUPSFILTER)/foo2qpdl-c410scms-wrapper
	install -D -m 644 c410scms.dat $(DESTDIR)$(DATADIR)/c410scms.dat

check: c410scms-filter
	$(PYTHON) -m unittest discover -s tests -v

clean:
	rm -f c410scms-filter c410scms.dat foo2qpdl-c410scms-wrapper

.PHONY: all data install check clean
