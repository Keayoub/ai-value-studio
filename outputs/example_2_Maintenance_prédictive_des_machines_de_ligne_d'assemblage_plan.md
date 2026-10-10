# AMOA Use Case Implementation Plan

## Métadonnées
- Date: 2026-10-04
- Organisation: IndustrieDemo
- Programme: AI Value Studio
- Département: Maintenance et Fiabilité
- Owner: Responsable Maintenance
- AI-assisted kickstart: Oui

## 1) Cadrage métier
- Titre du use case: Maintenance prédictive par IA
- Problem statement: Les pannes non planifiées des machines critiques entraînent des pertes de production importantes et des coûts de réparation élevés.
- Solution IA proposée: Solution d'analyse des signaux de capteurs en temps réel avec modèles d'apprentissage automatique pour prédire les défaillances avant qu'elles ne surviennent, en déclenchant des interventions de maintenance ciblées.
- Validation humaine obligatoire: Validation quotidienne des alertes par un technicien de maintenance avant intervention

## 2) Valeur business estimée
- Annual Time Value: 500000.0
- Error Avoidance Value: 1000000.0
- Estimated Gross Value: 1500000.0
- Estimated Net Value: 1350000.0
- Priority Score: 4.2
- Catégorie portefeuille: Quick Win

## 3) KPI de pilotage
- Temps moyen entre pannes (MTBF)
- Taux de disponibilité des équipements
- Coût de maintenance par machine
- Nombre d'interventions de maintenance préventive

## 4) Dépendances SI et organisationnelles
- SCADA
- Historique des pannes
- Plateforme d'acquisition de données temps réel

## 5) Gouvernance & risques
- Faux positifs entraînant des maintenances inutiles
- Drift des capteurs nécessitant recalibrage
- Intégration avec le SCADA existant

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
