# TIFINIA AI Value Studio — Spécifications fonctionnelles v0.1

> **Objectif :** construire une application Web qui guide un client et un consultant à travers un wizard d'AMOA IA, transforme les réponses en use cases structurés, calcule leur valeur et génère automatiquement les documents de décision.

## 1. Vision produit

AI Value Studio est le workspace de décision qui transforme un problème métier en use case IA priorisé, documenté et prêt à piloter.

```text
Programme client
  → Discovery
  → Use Case Canvas
  → Business Value Assessment
  → Readiness & Risk Assessment
  → Prioritization
  → Business Case
  → Pilot Charter
  → Roadmap
```

## 2. Naming et positionnement officiel

### Nom du produit

# TIFINIA AI Value Studio

### Description courte

> La plateforme d'AMOA IA pour identifier, évaluer et prioriser les cas d'usage à forte valeur business.

### Tagline

> De l'idée IA au cas d'usage finançable et activable.

### Pourquoi "Value Studio"

- **Value** positionne le produit sur le résultat métier : productivité, réduction des coûts, revenus, qualité, capacité et maîtrise du risque.
- **Studio** exprime un espace de travail collaboratif où le consultant et le client construisent ensemble les use cases, les business cases et la roadmap.
- Le nom reste extensible : framework de conseil, application Web, workspace collaboratif, moteur de scoring et porte d'entrée vers TIFINIA AI Platform.
- Le nom évite de réduire le produit à un simple questionnaire, à un outil de scoring ou à un générateur de documents.

### Description anglaise

> A structured advisory and decision platform for discovering, assessing and prioritizing AI use cases.

### Architecture de gamme

```text
TIFINIA AI Value Studio
  → découvre et priorise les opportunités
TIFINIA AI Platform
  → gouverne et opère les capacités IA
TIFINIA Agent Studio
  → conçoit et teste les agents et workflows
TIFINIA AI Solutions
  → applique l'IA aux verticales métier
```

## 3. Verticalisation et capacités transverses

Le framework conserve un **Core Framework horizontal** et ajoute des **Vertical Packs**. Les règles de discovery, scoring, readiness, gouvernance et génération documentaire restent communes. Les questions, KPI, risques et exemples de use cases sont adaptés au secteur.

### Vertical Packs initiaux

- Talent / RH
- Customer Support
- Compliance & Finance
- Secteur public
- Santé
- Juridique

### Capacité transverse prioritaire : AI Case Processing

**AI Case Processing** est un use case réutilisable pour analyser, compléter, qualifier, résumer et faire progresser des dossiers métier composés de plusieurs documents, étapes et décisions.

Exemples de déclinaisons :

- dossier patient ou dossier de prise en charge ;
- dossier de remboursement mutualiste ou assurance ;
- dossier de crédit ;
- dossier de candidature ou recrutement ;
- dossier de conformité ;
- dossier de financement public ;
- dossier fournisseur ou procurement ;
- dossier juridique.

Le framework doit traiter ce cas comme une capability packagée, avec :

- ingestion de documents et métadonnées ;
- classification du dossier ;
- extraction des champs et pièces ;
- détection des éléments manquants ;
- vérification de cohérence ;
- résumé du dossier ;
- scoring ou recommandation ;
- routage vers le bon workflow ;
- validation humaine ;
- journalisation et traçabilité de la décision.

Le système ne doit pas présenter une recommandation comme une décision automatique lorsque la validation humaine, réglementaire ou métier est requise.

## 4. Utilisateurs et rôles

### Consultant / AI Advisor

- crée un client et un programme ;
- configure les ateliers et questionnaires ;
- conduit ou assiste les interviews ;
- modifie les réponses et les scores ;
- ajoute les hypothèses et preuves ;
- valide les recommandations ;
- génère et partage les documents.

### Client Sponsor / Executive

- consulte les programmes autorisés ;
- répond aux questions métier ;
- commente les use cases ;
- valide ou rejette une recommandation ;
- télécharge les livrables exécutifs.

### Contributor métier

- répond aux questions de son périmètre ;
- documente le processus actuel ;
- confirme les volumes, coûts et irritants ;
- valide les KPI et hypothèses.

### Workspace Admin

- gère les utilisateurs, organisations et rôles ;
- gère les templates de questionnaires ;
- configure branding, langue et paramètres du workspace.

## 4. Principes UX

- Un écran = une décision ou une question principale.
- Progression visible et sauvegarde automatique.
- Possibilité de reprendre un wizard interrompu.
- Les questions complexes affichent un exemple et une aide contextuelle.
- Le consultant peut passer en mode interview et saisir les réponses pour le client.
- Toute recommandation générée par IA doit afficher ses hypothèses et rester éditable.
- Le score n'est jamais présenté comme une vérité automatique : il est accompagné d'une justification et d'un niveau de confiance.
- Interface prioritairement en français, structure prête pour anglais et arabe RTL.

## 5. Navigation principale

- Dashboard
- Organisations
- Programmes
- Use cases
- Portfolio
- Documents
- Templates
- Settings

## 6. Parcours principal : création d'un programme

### 5.1 Créer une organisation

Champs obligatoires :

- nom ;
- secteur ;
- pays / région ;
- taille approximative ;
- langue de travail ;
- description courte ;
- sponsor principal.

Résultat : organisation créée avec workspace isolé.

### 5.2 Créer un programme AI Value Assessment

Champs :

- nom du programme ;
- objectif stratégique ;
- départements concernés ;
- période ;
- sponsor ;
- consultant responsable ;
- nombre cible de use cases ;
- modèle de questionnaire ;
- niveau de confidentialité.

États du programme : `Draft`, `Discovery`, `Assessment`, `Prioritization`, `Decision`, `Closed`.

### 5.3 Dashboard du programme

Le dashboard doit afficher :

- progression globale ;
- nombre de use cases par statut ;
- score moyen de valeur et de faisabilité ;
- top 5 des opportunités ;
- informations manquantes ;
- validations en attente ;
- documents générés ;
- prochaine action recommandée.

## 7. Wizard de création d'un use case

Le wizard est sauvegardé étape par étape. Chaque étape affiche `Précédent`, `Sauvegarder et quitter`, `Continuer` et, lorsque pertinent, `Passer en revue`.

### Étape 0 — Kickstart LLM (optionnel)

Avant l'étape 1, le consultant peut lancer un assistant de démarrage pour générer un premier brouillon éditable du use case à partir de quelques entrées minimales :

- objectif stratégique ;
- processus ciblé ;
- principale friction actuelle ;
- département et population impactée ;
- contraintes critiques (réglementaires, sécurité, SLA).

Sorties proposées par l'assistant (toujours éditables) :

- problem statement ;
- proposition de solution IA ;
- KPI initiaux ;
- hypothèses de valeur ;
- risques initiaux ;
- informations manquantes à confirmer.

Toutes les suggestions sont marquées `AI-assisted` et ne valent jamais validation automatique.

### Étape 1 — Contexte et processus

Questions :

- Quel processus voulez-vous améliorer ?
- Quelle équipe est concernée ?
- Qui réalise actuellement le travail ?
- Quel est le déclencheur ?
- Quelles sont les étapes principales ?
- Quels systèmes sont utilisés ?
- Quel est le volume et la fréquence ?
- Combien de temps prend une occurrence ?

Sortie : Process Map simplifiée.

### Étape 2 — Problème et friction

Questions :

- Quel est le problème précis ?
- Qu'est-ce qui rend le processus lent, coûteux ou risqué ?
- Où les erreurs apparaissent-elles ?
- Quelle connaissance manque aux utilisateurs ?
- Quel est le coût estimé de l'inaction ?
- Pourquoi le sujet est-il prioritaire maintenant ?

Sortie : Problem Statement avec impact et preuve.

### Étape 3 — Solution IA envisagée

Questions :

- Que devrait faire l'IA ?
- Quelles informations reçoit-elle ?
- Quelle sortie doit-elle produire ?
- L'IA assiste-t-elle, recommande-t-elle ou exécute-t-elle ?
- Quelle validation humaine est obligatoire ?
- Dans quelles langues ?
- Quel comportement est explicitement interdit ?

Sortie : AI Use Case Canvas initial.

### Étape 4 — Valeur business

Questions chiffrées ou estimées :

- volume mensuel / annuel ;
- temps moyen actuel ;
- coût horaire ou coût par transaction ;
- taux d'erreur actuel ;
- coût d'une erreur ;
- revenus ou capacité concernés ;
- réduction attendue ;
- délai avant impact ;
- KPI principal et valeur cible.

Le système calcule une estimation indicative :

```text
Annual Time Value = volume annuel × temps économisé × coût horaire
Error Avoidance Value = volume annuel × réduction d'erreurs × coût moyen d'une erreur
Estimated Gross Value = Annual Time Value + Error Avoidance Value + Revenue/Capacity Value
Estimated Net Value = Estimated Gross Value - Estimated Annual Cost
```

Toutes les hypothèses sont visibles, éditables et versionnées.

### Étape 5 — Data readiness

Questions :

- Quelles sont les sources de données ?
- Les données sont-elles disponibles ?
- Sont-elles structurées, documentaires ou multimodales ?
- Quelle est leur qualité estimée ?
- Qui en est le propriétaire ?
- Sont-elles accessibles pour un pilote ?
- Contiennent-elles des données personnelles ou sensibles ?
- Quels connecteurs sont nécessaires ?

Sortie : Data Readiness score + liste des gaps.

### Étape 6 — Technical & operational readiness

Questions :

- Quels systèmes doivent être intégrés ?
- Quel environnement de déploiement est accepté ?
- Quelles contraintes de latence et disponibilité existent ?
- Quelles compétences sont disponibles ?
- Qui supportera la solution ?
- Quelles formations sont nécessaires ?
- Quelles dépendances peuvent bloquer le pilote ?

Sortie : Readiness score + dépendances.

### Étape 7 — Risk & governance

Questions :

- Quel est l'impact d'une mauvaise réponse ?
- L'IA prend-elle une décision affectant une personne ?
- Une explication est-elle obligatoire ?
- Une validation humaine est-elle requise ?
- Quelles données ne doivent jamais sortir du périmètre ?
- Quels logs et éléments d'audit sont nécessaires ?
- Quel niveau d'accès faut-il appliquer ?

Sortie : Risk profile avec niveau `Low`, `Medium`, `High`, `Critical`.

### Étape 8 — Revue et soumission

L'écran affiche :

- résumé du problème ;
- solution IA proposée ;
- valeur estimée ;
- scores de readiness ;
- risques ;
- hypothèses ;
- informations manquantes ;
- recommandation préliminaire.

Actions : `Soumettre pour revue`, `Demander des informations`, `Enregistrer comme brouillon`.

## 8. Scoring et priorisation

### 7.1 Dimensions

| Dimension | Poids |
|---|---:|
| Business value | 25 % |
| Current friction | 15 % |
| Data feasibility | 15 % |
| Technical feasibility | 15 % |
| Adoption potential | 10 % |
| Risk & governance | 20 % |

Chaque dimension reçoit une note de 1 à 5, une justification et un niveau de confiance.

### 7.2 Règles de calcul

```text
Priority Score = Σ(note × poids)
```

Le système doit conserver :

- notes individuelles ;
- auteur de la note ;
- justification ;
- date ;
- version du scoring ;
- éventuelle surcharge manuelle ;
- raison de la surcharge.

### 7.3 Catégorisation

- `Quick Win` : valeur forte, faisabilité forte, risque maîtrisé ;
- `Strategic Bet` : valeur forte, mais effort ou dépendances élevés ;
- `Foundation` : prérequis data, sécurité ou intégration ;
- `Defer` : valeur ou readiness insuffisante ;
- `Reject` : problème mal défini ou risque disproportionné.

Une surcharge manuelle requiert un commentaire du consultant.

## 9. Portfolio view

La vue Portfolio doit permettre :

- vue tableau ;
- matrice valeur / faisabilité ;
- filtres par département, statut, score, risque et sponsor ;
- comparaison de plusieurs use cases ;
- regroupement en initiatives ;
- sélection des use cases à inclure dans la roadmap ;
- export image ou PDF de la matrice.

## 10. Cas d'usage phare : AI Case Processing

AI Case Processing est une capacité transverse de TIFINIA AI Value Studio et un candidat prioritaire pour les pilotes clients.

### Définition

> Transformer un dossier métier hétérogène en un dossier structuré, contrôlé, résumé et prêt pour décision ou traitement.

### Chaîne fonctionnelle

```text
Réception
→ classification
→ extraction
→ contrôle de complétude
→ vérification de cohérence
→ synthèse
→ recommandation
→ validation humaine
→ routage / action
→ audit
```

### Questions spécifiques d'assessment

- Quel type de dossier est traité ?
- Combien de dossiers sont reçus par période ?
- Combien de documents contient un dossier moyen ?
- Quels formats et canaux sont utilisés ?
- Quelles pièces sont obligatoires ?
- Quelles informations doivent être extraites ?
- Quelles incohérences ou fraudes faut-il détecter ?
- Quelle décision ou action suit le traitement ?
- Quel délai de traitement est attendu ?
- Quel niveau de validation humaine est obligatoire ?
- Quel est le coût d'un dossier incomplet ou mal traité ?
- Quelles données personnelles, médicales ou financières sont présentes ?

### KPI possibles

- délai moyen de traitement ;
- taux de dossiers complets au premier passage ;
- taux d'extraction correcte ;
- taux de dossiers routés automatiquement ;
- temps humain par dossier ;
- taux d'erreur ou de reprise ;
- taux de respect du SLA ;
- taux de validation humaine ;
- coût moyen par dossier ;
- satisfaction de l'agent et du demandeur.

### Garde-fous

- validation humaine pour les décisions à impact ;
- citation de la pièce ou de la donnée source ;
- journal de toutes les modifications ;
- séparation entre extraction, recommandation et décision ;
- gestion des dossiers incomplets et des exceptions ;
- contrôle d'accès par dossier et par rôle ;
- conservation et suppression selon la politique client.

### Déclinaisons verticales

| Verticale | Exemple de dossier | Décision ou action |
|---|---|---|
| Santé | dossier patient / prise en charge | compléter, orienter, préparer la revue |
| Mutuelle / assurance | dossier de remboursement | contrôler, qualifier, router |
| Crédit | dossier de demande de financement | vérifier, scorer, envoyer en comité |
| RH | dossier candidat | extraire, matcher, préparer l'entretien |
| Compliance | dossier KYC / contrôle | détecter les manquants, escalader |
| Public | dossier d'aide ou de financement | vérifier l'éligibilité, instruire |

## 11. Génération documentaire

### 11.1 Documents générés

À partir des données du programme et des use cases :

- Use Case Canvas ;
- Business Value Assessment ;
- AI Readiness Assessment ;
- Risk & Governance Profile ;
- Executive AI Opportunity Brief ;
- AMOA Use Case Implementation Plan ;
- Portfolio Prioritization Report ;
- Pilot Charter ;
- AI Roadmap ;
- Decision Pack.

### 9.2 Formats

MVP :

- PDF ;
- DOCX ;
- Markdown.

Phase suivante :

- PowerPoint ;
- export JSON ;
- export XLSX ;
- lien de partage sécurisé.

### 9.3 Règles de génération

- version du document affichée ;
- date et auteur affichés ;
- hypothèses séparées des faits ;
- scores et calculs détaillés ;
- contenu généré par IA marqué comme `AI-assisted` ;
- aucun document ne doit être présenté comme validé sans validation explicite ;
- régénérer une nouvelle version au lieu d'écraser une version approuvée.

## 11. Assistance IA

L'assistant IA peut :

- reformuler un problème métier ;
- détecter les informations manquantes ;
- kickstarter un brouillon de use case au démarrage du wizard ;
- proposer des use cases à partir d'un processus ;
- suggérer des KPI ;
- résumer une interview ;
- identifier des hypothèses non prouvées ;
- proposer une première note avec justification ;
- générer un executive summary ;
- repérer des use cases similaires ou doublons.

Contraintes :

- l'IA ne valide jamais seule un use case ;
- chaque suggestion est éditable ;
- chaque suggestion affiche sa source ou son hypothèse ;
- aucune donnée client ne doit être utilisée pour entraîner un modèle sans consentement explicite ;
- les prompts et sorties sensibles doivent être journalisés selon la politique du workspace.

## 12. Modèle de données fonctionnel

### Organisation

- id, name, sector, country, default_language, sponsor_id, created_at.

### Workspace

- id, organization_id, branding, enabled_languages, confidentiality_policy.

### Program

- id, workspace_id, name, objective, status, sponsor_id, consultant_id, start_date, target_date.

### UseCase

- id, program_id, title, department, owner_id, status, category, priority_score, confidence_level.

### Assessment

- id, use_case_id, type, version, status, author_id, submitted_at, approved_at.

### Answer

- id, assessment_id, question_key, value, evidence, confidence, author_id, updated_at.

### Score

- id, use_case_id, dimension, weight, value, justification, confidence, author_id, version.

### Hypothesis

- id, use_case_id, statement, value, status, owner_id, validation_date.

### Document

- id, program_id, use_case_id, type, version, format, status, storage_url, generated_by, approved_by.

### Comment / Approval

- id, target_type, target_id, author_id, body, status, created_at.

## 13. Permissions

- Un client ne voit que son workspace.
- Un contributor ne voit que les programmes auxquels il est affecté.
- Un sponsor peut approuver mais ne modifie pas les règles globales de scoring.
- Un consultant peut modifier les réponses mais les changements importants sont historisés.
- Un admin peut configurer les templates mais ne peut pas lire les données d'un autre workspace sans permission.

## 14. MVP recommandé

### Inclus dans le MVP

- authentification et workspace ;
- création organisation / programme ;
- kickstart LLM optionnel au démarrage du wizard ;
- wizard use case en 8 étapes ;
- autosave et reprise ;
- scorecard manuelle assistée ;
- calcul de priorité ;
- portfolio matrix ;
- génération Markdown et PDF ;
- génération d'un document AMOA de mise en place du use case ;
- rôles Consultant, Sponsor, Contributor ;
- audit minimal des changements ;
- interface française avec fondation i18n.

### Hors périmètre MVP

- exécution de workflows IA ;
- intégration profonde à TIFINIA Platform ;
- facturation ;
- marketplace ;
- benchmark inter-clients ;
- entraînement de modèles propriétaires ;
- PowerPoint avancé ;
- application mobile.

## 15. Critères d'acceptation principaux

### Wizard

- Un utilisateur peut créer un use case sans perdre ses réponses en quittant l'écran.
- Une validation de champ indique clairement ce qui manque.
- Le consultant peut remplir le wizard en mode interview.
- La progression est visible et le statut est persisté.

### Scoring

- Le score est recalculé quand une note ou un poids change.
- Les notes sont accompagnées d'une justification.
- Toute surcharge manuelle est historisée.
- Le système catégorise le use case et affiche les règles utilisées.

### Documents

- Un document généré contient les données du dernier état validé.
- Une nouvelle génération crée une nouvelle version.
- Les hypothèses, scores et risques apparaissent dans le document.
- Un document approuvé ne peut pas être modifié sans créer une nouvelle version.

### Sécurité

- Un utilisateur ne peut pas accéder à un autre workspace par modification d'URL ou d'identifiant.
- Les permissions sont vérifiées côté serveur.
- Les actions sensibles sont présentes dans l'audit log.

## 16. Backlog de construction

### Epic 1 — Foundation

- auth, workspace, rôles ;
- organisations et programmes ;
- navigation et design system ;
- audit log minimal.

### Epic 2 — Use Case Wizard

- modèle de questionnaire ;
- rendu des types de questions ;
- autosave ;
- validation ;
- mode interview ;
- revue et soumission.

### Epic 3 — Assessment Engine

- scorecard ;
- calculs de valeur ;
- scoring pondéré ;
- hypothèses ;
- readiness et risk profiles.

### Epic 4 — Portfolio

- liste et filtres ;
- matrice ;
- comparaison ;
- catégorisation ;
- roadmap initiale.

### Epic 5 — Documents

- templates Markdown ;
- génération PDF ;
- versioning ;
- téléchargement ;
- statut draft / review / approved.

### Epic 6 — AI Copilot

- détection de gaps ;
- résumé d'interview ;
- suggestions de use cases ;
- suggestions de KPI ;
- génération executive summary avec validation humaine.

## 17. Definition of Done MVP

- Un consultant peut créer un programme complet.
- Il peut documenter au moins 3 use cases via le wizard.
- Le système calcule les scores et produit une matrice portfolio.
- Un sponsor peut commenter et approuver une recommandation.
- Le système génère un Executive Brief et un Pilot Charter en PDF.
- Les données sont isolées entre workspaces.
- Les parcours critiques ont des tests automatisés.
- La documentation de démarrage est incluse dans le repository.
