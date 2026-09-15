# Build the report.
#
#   make            compile main.pdf
#   make figures    refresh figures/ from the simulation output
#   make clean      remove build artefacts
#
# Requires a LaTeX distribution with biblatex and biber (MacTeX, TeX Live),
# or tectonic. biblatex and biber versions must match; see the compatibility
# matrix in the biblatex manual if biber reports a control-file version error.

TEX      := main.tex
PDF      := main.pdf
REPO     := ../..
RESULTS  := $(REPO)/results/figures

.PHONY: all figures clean distclean tectonic

all: $(PDF)

$(PDF): $(TEX) sample.bib $(wildcard figures/*.png)
	latexmk -pdf -bibtex- $(TEX) || $(MAKE) tectonic

# Fallback / alternative engine. Tectonic fetches packages on demand.
tectonic:
	tectonic -X compile $(TEX)

# Regenerate the figures from the simulation. Run the study first if
# results/ is empty:  python scripts/run_all.py
figures:
	@test -d $(RESULTS) || { \
	  echo "No $(RESULTS). Run 'python scripts/run_all.py' from the repo root first."; \
	  exit 1; }
	cp $(RESULTS)/*.png figures/
	@echo "figures refreshed from $(RESULTS)"

clean:
	rm -f *.aux *.bbl *.bcf *.blg *.log *.out *.run.xml *.toc *.fls *.fdb_latexmk

distclean: clean
	rm -f $(PDF)
