# AMOA Use Case Implementation Plan

## Métadonnées
- Date: 2026-10-04
- Organisation: Banque Demo
- Programme: AI Value Studio
- Département: Lutte contre le blanchiment (AML)
- Owner: Responsable Conformité
- AI-assisted kickstart: Oui

## 1) Cadrage métier
- Titre du use case: Surveillance IA des Transactions Suspectes
- Problem statement: Analyse manuelle lente des transactions, taux de faux positifs élevé entraînant des coûts d'enquête inutile
- Solution IA proposée: Assistant IA de scoring de risque en temps réel avec explication des facteurs de risque et validation humaine obligatoire pour les alertes critiques
- Validation humaine obligatoire: Validation manuelle obligatoire pour les alertes au-dessus d'un seuil de risque

## 2) Valeur business estimée
- Annual Time Value: 80000000.0
- Error Avoidance Value: 500000000.0
- Estimated Gross Value: 580000000.0
- Estimated Net Value: 579850000.0
- Priority Score: 4.2
- Catégorie portefeuille: Quick Win

## 3) KPI de pilotage
- Temps moyen d'analyse par transaction
- Taux de faux positifs
- Nombre d'enquêtes déclenchées
- Coût par enquête

## 4) Dépendances SI et organisationnelles
- Système de core bancaire
- Outil de gestion des alertes
- Base de données de référence

## 5) Gouvernance & risques
- Biais algorithmique
- Erreurs de classification (faux positifs/négatifs)
- Conformité réglementaire (RGPD, LCB-FT)

## 6) Plan de mise en place
### Phase 1 — Discovery & Design (Semaines 1-2)
- Valider les hypothèses et le périmètre
- Cartographier données + règles métier
- Définir protocole human-in-the-loop

### Phase 2 — Pilot Build (Semaines 3-6)
- Implémenter flux IA assisté
- Tester qualité, sécurité, conformité
- Former utilisateurs pilotes

### Phase 3 — Go/No-Go & Scale (Semaines 7-8)
- Mesurer KPI cibles vs baseline
- Décider Go/Defer/Reject
- Préparer feuille de route d'industrialisation

## 7) Décision et validation
- Sponsor décision: __________________
- Décision: Go / Pilot / Defer / Reject
- Date de revue: __________________
