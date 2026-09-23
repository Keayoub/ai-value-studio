# Coding Agent Brief — TIFINIA AI Value Studio MVP

## Mission

Construire le MVP Web de **TIFINIA AI Value Studio**, une plateforme d'AMOA IA qui aide un consultant et son client à identifier, cadrer, évaluer et prioriser des cas d'usage IA, puis à générer les documents de décision et de pilotage.

## Proposition de valeur

> Transformer les idées IA d'une organisation en cas d'usage prioritaires, chiffrés, gouvernés et prêts à piloter.

Le produit se situe entre la stratégie métier et l'exécution technologique :

```text
Business problem
→ AI use case
→ Business value
→ Feasibility
→ Risk & governance
→ Prioritized pilot
→ TIFINIA implementation
```

## Produit et architecture de gamme

Nom officiel : **TIFINIA AI Value Studio**

Tagline : **De l'idée IA au cas d'usage finançable et activable.**

- AI Value Studio : découvre et priorise les opportunités.
- TIFINIA AI Platform : gouverne et opère les capacités IA.
- TIFINIA Agent Studio : conçoit et teste les agents et workflows.
- TIFINIA AI Solutions : applique l'IA aux verticales métier.

## Références à lire avant de coder

- `README.md`
- `docs/FUNCTIONAL_SPECIFICATIONS_FR.md`
- `commercial-assets/product-frameworks/TIFINIA_AI_VALUE_STUDIO_PRODUCT_BRIEF_FR.md`
- `commercial-assets/product-frameworks/templates/AI_USE_CASE_CANVAS_FR.md`
- `commercial-assets/product-frameworks/templates/AI_VALUE_SCORECARD_FR.md`
- `commercial-assets/product-frameworks/templates/AI_PORTFOLIO_MATRIX_FR.md`
- `commercial-assets/product-frameworks/templates/EXECUTIVE_AI_OPPORTUNITY_BRIEF_FR.md`

## Scope MVP

### Inclus

1. Authentification et workspace multi-tenant.
2. Organisations et programmes d'assessment.
3. Rôles : Consultant, Sponsor, Contributor, Workspace Admin.
4. Dashboard programme.
5. Wizard de création d'un use case en 8 étapes.
6. Autosave, reprise et validation des réponses.
7. Mode interview pour que le consultant remplisse le wizard avec le client.
8. Scorecard business value / readiness / risk.
9. Calcul du Priority Score pondéré.
10. Portfolio list et matrice valeur / faisabilité.
11. Commentaires, revue et approbation.
12. Génération de documents Markdown et PDF.
13. Versioning des documents.
14. Audit log minimal.
15. Interface française avec fondation i18n prête pour EN et AR RTL.

### Hors périmètre MVP

- facturation ;
- marketplace ;
- benchmark inter-clients ;
- exécution de workflows IA ;
- intégration profonde à TIFINIA AI Platform ;
- application mobile ;
- PowerPoint avancé ;
- entraînement de modèles propriétaires.

## Parcours critique à implémenter

### 1. Programme

Consultant :

```text
Créer organisation
→ créer programme
→ choisir template d'assessment
→ inviter sponsor/contributors
→ ouvrir dashboard
```

### 2. Use case wizard

Étapes obligatoires :

1. Contexte et processus
2. Problème et friction
3. Solution IA envisagée
4. Valeur business
5. Data readiness
6. Technical & operational readiness
7. Risk & governance
8. Revue et soumission

Chaque étape doit avoir :

- progression visible ;
- sauvegarde automatique ;
- validation claire ;
- `Précédent` ;
- `Sauvegarder et quitter` ;
- `Continuer` ;
- reprise après interruption.

### 3. Revue et décision

Le consultant doit pouvoir :

- soumettre un use case ;
- demander des informations ;
- ajouter des justifications ;
- surcharger un score avec commentaire ;
- recommander `Go`, `Pilot`, `Defer` ou `Reject`.

Le sponsor doit pouvoir :

- commenter ;
- approuver ;
- rejeter ;
- demander une modification.

## Scoring

Dimensions et poids :

| Dimension | Poids |
|---|---:|
| Business value | 25 % |
| Current friction | 15 % |
| Data feasibility | 15 % |
| Technical feasibility | 15 % |
| Adoption potential | 10 % |
| Risk & governance | 20 % |

```text
Priority Score = Σ(note × poids)
```

Chaque note est entre 1 et 5 et doit contenir :

- justification ;
- niveau de confiance ;
- auteur ;
- date ;
- version du scoring.

Catégories :

- Quick Win ;
- Strategic Bet ;
- Foundation ;
- Defer ;
- Reject.

Une surcharge manuelle nécessite un commentaire et doit être historisée.

## Business value assessment

Supporter les variables suivantes :

- volume mensuel / annuel ;
- temps moyen actuel ;
- temps économisé estimé ;
- coût horaire ;
- taux d'erreur ;
- coût moyen d'une erreur ;
- revenu ou capacité impactée ;
- coût annuel estimé de la solution.

Calculs indicatifs :

```text
Annual Time Value = volume annuel × temps économisé × coût horaire
Error Avoidance Value = volume annuel × réduction d'erreurs × coût moyen d'une erreur
Estimated Gross Value = Annual Time Value + Error Avoidance Value + Revenue/Capacity Value
Estimated Net Value = Estimated Gross Value - Estimated Annual Cost
```

Toujours afficher les hypothèses et permettre leur modification.

## Capability transverse prioritaire : AI Case Processing

Prévoir dans le modèle de données et les templates un capability pack transversal pour les dossiers métier :

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

Déclinaisons :

- dossier patient / prise en charge ;
- dossier mutuelle / assurance ;
- dossier de crédit ;
- dossier candidat RH ;
- dossier KYC / compliance ;
- dossier d'aide publique ;
- dossier fournisseur ;
- dossier juridique.

Prévoir au minimum les champs / questions suivants :

- type de dossier ;
- volume ;
- nombre moyen de documents ;
- pièces obligatoires ;
- champs à extraire ;
- incohérences à détecter ;
- décision ou action suivante ;
- SLA ;
- niveau de validation humaine ;
- coût d'un dossier incomplet ou mal traité ;
- présence de données personnelles, médicales ou financières.

Garde-fous :

- aucune décision à impact sans validation humaine configurable ;
- source documentaire visible ;
- séparation extraction / recommandation / décision ;
- audit log ;
- gestion des exceptions ;
- accès par dossier et rôle.

## Modèle de données minimal

Créer les entités suivantes :

- `Organization`
- `Workspace`
- `User`
- `Program`
- `UseCase`
- `Assessment`
- `Question`
- `Answer`
- `Score`
- `Hypothesis`
- `Comment`
- `Approval`
- `Document`
- `AuditEvent`

Les données doivent être isolées par workspace côté serveur. Ne jamais faire confiance à l'identifiant fourni par le frontend sans vérifier les permissions.

## Documents à générer

MVP :

- AI Use Case Canvas ;
- Business Value Assessment ;
- AI Readiness Assessment ;
- Risk & Governance Profile ;
- Executive AI Opportunity Brief ;
- Portfolio Prioritization Report ;
- Pilot Charter ;
- AI Roadmap.

Formats MVP : Markdown et PDF.

Règles :

- nouvelle version au lieu d'écraser un document approuvé ;
- afficher date, auteur et version ;
- séparer faits, hypothèses et recommandations ;
- marquer le contenu assisté par IA ;
- ne jamais afficher un document comme approuvé sans approbation explicite.

## Assistance IA — MVP limité

Prévoir une abstraction de service pour pouvoir ajouter ensuite :

- détection d'informations manquantes ;
- résumé d'interview ;
- reformulation d'un problème ;
- suggestion de KPI ;
- détection de doublons ;
- génération d'executive summary.

L'IA ne valide jamais seule un use case et toutes ses sorties restent éditables.

## UX / UI

Direction visuelle :

- premium B2B ;
- sobre et claire ;
- forte lisibilité ;
- design orienté workflow ;
- cartes de score ;
- progression visible ;
- vue portfolio avec matrice ;
- responsive desktop-first ;
- français par défaut ;
- architecture compatible anglais et arabe RTL.

Écrans MVP :

1. Login
2. Workspace dashboard
3. Organisation detail
4. Programme dashboard
5. New use case wizard
6. Use case detail / review
7. Assessment scorecards
8. Portfolio matrix
9. Document center
10. Settings / users / templates

## Critères d'acceptation critiques

- Un consultant peut créer une organisation et un programme.
- Il peut documenter au moins 3 use cases sans perdre ses réponses.
- Le mode interview permet de saisir les réponses au nom du client.
- Le score est recalculé correctement après modification d'une note.
- Toute surcharge de score est historisée.
- Un sponsor peut commenter et approuver.
- Un use case peut être exporté en Executive Brief et Pilot Charter PDF.
- Un document approuvé ne peut pas être écrasé.
- Un workspace ne peut jamais accéder aux données d'un autre workspace.
- Les actions sensibles apparaissent dans l'audit log.
- Les parcours critiques ont des tests automatisés.

## Méthode d'implémentation recommandée

1. Inspecter le repository avant tout changement.
2. Choisir et documenter la stack cible avant de coder.
3. Construire d'abord le modèle de données et l'isolation workspace.
4. Implémenter le wizard avec données persistées avant l'assistance IA.
5. Ajouter scoring et business value avec tests unitaires.
6. Ajouter portfolio et revue / approbation.
7. Ajouter génération Markdown puis PDF.
8. Ajouter l'assistance IA derrière une interface de service.
9. Tester les permissions, les parcours critiques et la génération documentaire.
10. Ne pas implémenter de fonctionnalités hors périmètre MVP sans décision explicite.

## Définition de Done

Le MVP est terminé lorsque le parcours suivant fonctionne de bout en bout :

```text
Login
→ créer workspace
→ créer programme
→ créer use case
→ répondre aux 8 étapes
→ calculer valeur et scores
→ soumettre pour revue
→ approuver
→ générer Executive Brief PDF
→ générer Pilot Charter PDF
→ consulter la matrice portfolio
```

Toutes les étapes doivent être vérifiables avec des tests et sans données fictives présentées comme des résultats réels.
