BINARY  := check-git-branch
INSTALL := $(HOME)/bin/$(BINARY)

.PHONY: all build install clean

all: build

build:
	go build -o $(BINARY) .

install:
	go build -o $(INSTALL) .
	chmod 0755 $(INSTALL)

clean:
	rm -f $(BINARY)
