# AI Value Studio - Exemples de livrables pour démonstration

Ce dossier contient des exemples de livrables générés par le framework AI Value Studio, prêts à être utilisés lors de démonstrations clients ou d'ateliers de découverte.

## Contenu

Chaque exemple comprend deux fichiers :
- Un document Word (.docx) contenant le plan d'implémentation AMOA complet.
- Une présentation PowerPoint (.pptx) résumant le use case, la valeur business estimée et le plan de mise en place.

## Liste des exemples

1. **RetailCo Demo - Moteur de recommandation personnalisée**
   - Use case : Moteur de recommandation basé sur le deep learning pour l'e-commerce.
   - Valeur business estimée : à voir dans le document.

2. **IndustrieDemo - Maintenance prédictive par IA**
   - Use case : Solution d'analyse des signaux de capteurs pour prédire les défaillances des machines critiques.
   - Valeur business estimée : à voir dans le document.

3. **EnergieDemo - Prévision de charge du réseau électrique intelligent**
   - Use case : Modèle de prévision de charge intégrant données historiques, météo et production renouvelable.
   - Valeur business estimée : à voir dans le document.

4. **AgenceSociale Demo - Détection de fraude dans les prestations sociales**
   - Use case : Système de notation de risque pour identifier les prestations sociales frauduleuses.
   - Valeur business estimée : à voir dans le document.

5. **Centre Hospitalier Universitaire Demo - Assistant de Triage IA pour les Urgences**
   - Use case : Assistant IA supervisé pour qualification, recommandation et validation humaine obligatoire aux urgences.
   - Valeur business estimée : 96 000 €/an (Valeur Nette).

6. **Banque Demo - Surveillance IA des Transactions Suspectes**
   - Use case : Assistant IA de scoring de risque en temps réel avec explication et validation humaine obligatoire.
   - Valeur business estimée : à voir dans le document.

7. **Client Démo - AI Case Processing - Remboursements**
   - Use case : Extraction et contrôle de complétude assistés par IA pour les dossiers de remboursement.
   - Valeur business estimée : 206 800 €/an (Valeur Nette).

## Comment générer un nouveau livrable

Pour créer un livrable à partir d'un nouveau use case fourni par un client :

1. Préparer un fichier JSON d'entrée suivant la structure utilisée dans le dossier `examples/` (voir un exemple comme `example_1_Moteur_de_recommandation_e_commerce.json`).
2. Placer ce JSON dans le dossier `examples/` (ou ailleurs).
3. Exécuter la commande suivante depuis la racine du projet :
   ```bash
   source .venv/bin/activate
   python -m ai_value_studio.cli --input <chemin/vers/votre_fichier.json> --output outputs/<nom_de_votre_fichier>_plan.md --kickstart
   ```
4. Le script de conversion (intégré dans ce dépôt) générera alors les fichiers `.docx` et `.pptx` dans le dossier `outputs/` avec le nom formaté comme `<Nom du Client> - <Titre du Use Case>.(docx|pptx)`.

## Notes

- Les valeurs de la Business Value Assessment (BVA) sont calculées automatiquement à partir des entrées fournies dans le JSON (volume annuel, temps économisé, coût horaire, réduction d'erreur, etc.).
- Le champ `kickstart_input` permet d'activer une génération IA du problem statement et de la solution si souhaité.
- Tous les fichiers sont prêts à être utilisés tels quels dans un contexte professionnel (envoi au client, présentation en comité de pilotage, etc.).

---
*Généré par AI Value Studio v0.1.0*
