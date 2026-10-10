# AI Value Studio - Livrables Professionnels

Ce dossier contient les livrables générés par le framework AI Value Studio au format Microsoft Word (.docx), prêts à être utilisés dans un contexte professionnel.

## Fichiers disponibles

1. **amoa_plan.docx** - Plan d'implémentation AMOA pour le use case générique de traitement des dossiers de remboursement
2. **amoa_health_plan.docx** - Plan d'implémentation AMOA pour un assistant de triage IA aux urgences (secteur santé)
3. **amoa_finance_plan.docx** - Plan d'implémentation AMOA pour une surveillance IA des transactions suspectes (secteur finance)

## Contenu de chaque livrable

Chaque document contient :
- Une page de couverture professionnelle avec le branding AI Value Studio
- Le plan d'implémentation AMOA complet structuré en 7 sections :
  1. Cadrage métier
  2. Valeur business estimée (avec calculs BVA)
  3. KPI de pilotage
  4. Dépendances SI et organisationnelles
  5. Gouvernance & risques
  6. Plan de mise en place (en 3 phases)
  7. Décision et validation

## Utilisation

Ces documents peuvent être :
- Distribués aux parties prenantes (sponsors, comités de pilotage)
- Utilisés comme base de discussion lors d'ateliers de validation
- Intégrés dans des dossiers de projet ou des présentations exécutives
- Modifiés directement dans Microsoft Word si nécessaire

## Génération

Ces fichiers ont été générés à partir des fichiers Markdown correspondants situés dans le même dossier, en utilisant un script de conversion qui applique :
- Une mise en forme professionnelle (police Calibri, couleurs corporate)
- Une structure de titre claire
- Une pagination et espacement optimisés pour la lecture

Pour régénérer ces documents à partir des sources Markdown :
```bash
# Depuis le répertoire racine du projet
cd /home/kay/projects/ai-value-studio
source .venv/bin/activate
python -c "
import os
from docx_utils import markdown_to_docx  # ou exécuter le script directement
# (le script de conversion serait exécuté ici)
"
```
