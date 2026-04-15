.PHONY: build install clean help

BINARY := tpuff

build:
	go build -o $(BINARY) .

install:
	go install .

clean:
	rm -f $(BINARY)

help:
	@echo "Available targets:"
	@echo "  build      - Build the binary"
	@echo "  install    - Install to GOPATH/bin"
	@echo "  clean      - Remove build artifacts"
