# AMOA Use Case Implementation Plan

## Métadonnées
- Date: 2026-10-04
- Organisation: AgenceSociale Demo
- Programme: AI Value Studio
- Département: Lutte contre la Fraude
- Owner: Directeur de la Lutte contre la Fraude
- AI-assisted kickstart: Oui

## 1) Cadrage métier
- Titre du use case: Détection de fraude dans les prestations sociales
- Problem statement: Les prestations sociales sont parfois attribuées à tort en raison de fausses déclarations ou de dissimulation de revenus, entraînant des pertes financières importantes pour l'État.
- Solution IA proposée: Système de notation de risque basé sur l'apprentissage automatique qui analyse les déclarations, l'historique des prestations, les données démographiques et les signaux externes pour attribuer un score de fraude à chaque demande, en déclenchant une enquête ciblée pour les scores élevés.
- Validation humaine obligatoire: Validation manuelle obligatoire des alertes à haut risque par un enquêteur avant toute décision de suspension ou de récupération

## 2) Valeur business estimée
- Annual Time Value: 8000000.0
- Error Avoidance Value: 200000000.0
- Estimated Gross Value: 208000000.0
- Estimated Net Value: 207750000.0
- Priority Score: 4.2
- Catégorie portefeuille: Quick Win

## 3) KPI de pilotage
- Taux de détection de la fraude
- Taux de faux positifs
- Coût moyen d'une enquête
- Montant récupéré

## 4) Dépendances SI et organisationnelles
- Système d'information des prestations
- Base de données des fraudes connues
- API de vérification d'identité

## 5) Gouvernance & risques
- Biais algorithmiques pouvant entraîner des discriminations
- Évolution des schémas de fraude nécessitant une ré-entraînement régulière
- Protection des données personnelles (RGPD)

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
