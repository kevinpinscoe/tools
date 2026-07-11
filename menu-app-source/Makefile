BINARY  := menu-app
INSTALL := $(HOME)/bin/$(BINARY)

# Derive the version from the latest menu-app-v* tag (e.g. "v1.0.0", or
# "v1.0.0-3-gabc123" when ahead of a tag). Falls back to "dev" outside git.
VERSION := $(shell git describe --tags --match 'menu-app-v*' --dirty 2>/dev/null | sed 's/^menu-app-v//')
ifeq ($(VERSION),)
VERSION := dev
endif
LDFLAGS := -X main.version=$(VERSION)

.PHONY: all build install clean

all: build

build:
	go build -ldflags "$(LDFLAGS)" -o $(BINARY) .

install:
	go build -ldflags "$(LDFLAGS)" -o $(INSTALL) .
	chmod 0755 $(INSTALL)

clean:
	rm -f $(BINARY)
