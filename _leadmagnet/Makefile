# Build the free-prompts lead-magnet PDF from HTML source.
# Writes both copies so they stay in sync.
#
# Usage (from repo root):
#   make -C _leadmagnet
#
# Dependency:
#   pip3 install "weasyprint==69.0"

PYTHON   := python3
SRC      := free-prompts.html
PDF      := openosint-free-prompts.pdf
DEST     := ../docs/assets/$(PDF)

.PHONY: all clean

all: $(PDF)
	cp $(PDF) $(DEST)
	@echo "Written: _leadmagnet/$(PDF)"
	@echo "Written: docs/assets/$(PDF)"

$(PDF): $(SRC) fonts/DejaVuSans.ttf fonts/DejaVuSans-Bold.ttf \
        fonts/DejaVuSans-Oblique.ttf fonts/DejaVuSansMono.ttf
	$(PYTHON) -m weasyprint $< $@

clean:
	rm -f $(PDF)
