"""Second keyword gate: articles the first gate dropped that name a youth term AND a movement term
(title + first 1,500 chars). Output data/relevance_candidates2.tsv. Reuses YOUTH from prefilter.py."""
import json, glob, os, re
MOVE = """mouvement movement movimiento movimento mobilisation mobilization mobilizaci mobilitazion movilizaci occup blocage
bloqueo collectif colectiv collettiv kolektiv bewegung ruch hnutí hnutie mozgalom движен мобилиз harakat حراك حركة κίνημα תנועה""".split()
