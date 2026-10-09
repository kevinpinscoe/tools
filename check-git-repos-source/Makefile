BINARY  := check-git-repos
INSTALL := $(HOME)/bin/$(BINARY)
INSTALL_LOCAL := $(HOME)/.local/bin/$(BINARY)

.PHONY: all build install install-local clean

all: build

build:
	go build -o $(BINARY) .

install:
	go build -o $(INSTALL) .
	chmod 0755 $(INSTALL)

install-local:
	mkdir -p $(dir $(INSTALL_LOCAL))
	go build -o $(INSTALL_LOCAL) .
	chmod 0755 $(INSTALL_LOCAL)

clean:
	rm -f $(BINARY)
