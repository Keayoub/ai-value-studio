'use client';

import { useEffect, useState, useMemo } from 'react';
import { Wizard } from 'react-wizard';

type Lang = 'fr' | 'en';
type Vertical = 'generic' | 'health' | 'insurance' | 'hr' | 'public' | 'finance';
type FieldKind = 'text' | 'number' | 'select';

type Question = {
  id: string;
  kind: FieldKind;
  label: Record<Lang, string>;
  help?: Record<Lang, string>;
  options?: { value: string; label: Record<Lang, string> }[];
  placeholder?: Record<Lang, string>;
};

type BvaInputs = {
  monthlyVolume: string;
  currentMinutes: string;
  targetMinutes: string;
  hourlyCost: string;
  currentErrorRate: string;
  targetErrorRate: string;
  errorCost: string;
  revenueCapacityValue: string;
  annualSolutionCost: string;
  implementationCostOneTime: string;
  implementationCostAnnual: string;
  discountRate: string;
  currency: string;
};

type Recommendation = {
  id: string;
  title: string;
  description: string;
  maturityAssessment: {
    data: number; // 1-5 scale
    process: number; // 1-5 scale
    technology: number; // 1-5 scale
    organization: number; // 1-5 scale
  };
  suggestedAISolutionType: string; // e.g., 'classification', 'forecasting', 'nlp', 'computer_vision'
  assumptions: string[];
  nextSteps: string[];
  effortEstimation: {
    preparation: number; // in weeks
    pilot: number; // in weeks
    scale: number; // in weeks
  };
};

type WizardState = {
  organization: string;
  sponsor: string;
  strategicObjective: string;
  targetProcess: string;
  currentFriction: string;
  impactedDepartment: string;
  criticalConstraints: string;
  useCaseTitle: string;
  vertical: Vertical;
  country: string;
  dynamicAnswers: Record<string, string>;
  generatedProblem: string;
  generatedSolution: string;
  hypotheses: string[];
  recommendations: Recommendation[];
  // BVA scenario fields
  bvaConservative: BvaInputs;
  bvaBase: BvaInputs;
  bvaOptimistic: BvaInputs;
  activeBvaScenario: 'conservative' | 'base' | 'optimistic';
  // New fields for Kickstart step
  timelineStart: string;
  timelineEnd: string;
  budgetRange: string;
  successMetrics: string[];
  stakeholders: string[];
  quantifiedPain: string;
};


const moroccoSpecificQuestions: Question[] = [
    { id: 'law_09_08_compliance', kind: 'select', label: { fr: 'Conformité à la loi 09-08 sur la protection des données personnelles', en: 'Compliance with Law 09-08 on personal data protection' }, options: [ { value: 'oui', label: { fr: 'Oui', en: 'Yes' } }, { value: 'partielle', label: { fr: 'Partielle', en: 'Partial' } }, { value: 'non', label: { fr: 'Non', en: 'No' } } ] },
    { id: 'cnpp_compliance', kind: 'select', label: { fr: 'Conformité aux référentiels du CNPP (Centre National de Prévention et de Protection)', en: 'CNPP compliance' }, options: [ { value: 'oui', label: { fr: 'Oui', en: 'Yes' } }, { value: 'en_cours', label: { fr: 'En cours', en: 'In progress' } }, { value: 'non', label: { fr: 'Non', en: 'No' } } ] },
    { id: 'language_requirements', kind: 'select', label: { fr: 'Exigences linguistiques (arabe, français)', en: 'Language requirements (Arabic, French)' }, options: [ { value: 'arabe_francais', label: { fr: 'Arabe et Français', en: 'Arabic and French' } }, { value: 'francais_seul', label: { fr: 'Français seul', en: 'French only' } }, { value: 'arabe_seul', label: { fr: 'Arabe seul', en: 'Arabic only' } } ] },
    { id: 'local_data_hosting', kind: 'select', label: { fr: 'Exigence d\'hébergement local des données', en: 'Local data hosting requirement' }, options: [ { value: 'obligatoire', label: { fr: 'Obligatoire', en: 'Mandatory' } }, { value: 'recommande', label: { fr: 'Recommandé', en: 'Recommended' } }, { value: 'pas_requis', label: { fr: 'Pas requis', en: 'Not required' } } ] },
    { id: 'sector_specific_regulator', kind: 'text', label: { fr: 'Régulateur sectoriel spécifique (ex: ANPN, AMMC, etc.)', en: 'Sector-specific regulator (e.g., ANPN, AMMC, etc.)' }, placeholder: { fr: 'Ex: ANPN pour télécoms, AMMC pour finance', en: 'e.g., ANPN for telecoms, AMMC for finance' } },
    { id: 'data_controller_name', kind: 'text', label: { fr: 'Nom du responsable du traitement', en: 'Data controller name' }, placeholder: { fr: 'Ex: Société XYZ', en: 'e.g., Company XYZ' } },
    { id: 'dpo_contact', kind: 'text', label: { fr: 'Coordonnées du Délégué à la Protection des Données (DPD)', en: 'Data Protection Officer (DPO) contact' }, placeholder: { fr: 'Ex: dpd@entreprise.ma', en: 'e.g., dpo@company.ma' } },
    { id: 'processing_register_exists', kind: 'select', label: { fr: 'Existence d\'un registre des traitements', en: 'Existence of a processing register' }, options: [ { value: 'oui', label: { fr: 'Oui', en: 'Yes' } }, { value: 'non', label: { fr: 'Non', en: 'No' } } ] },
    { id: 'data_retention_period', kind: 'text', label: { fr: 'Durée de conservation des données', en: 'Data retention period' }, placeholder: { fr: 'Ex: 3 ans après la fin du contrat', en: 'e.g., 3 years after contract end' } },
    { id: 'cross_border_transfer_safeguards', kind: 'text', label: { fr: 'Garanties pour les transferts transfrontaliers de données', en: 'Safeguards for cross-border data transfers' }, placeholder: { fr: 'Ex: Clauses contractuelles types, décision d\'adequation', en: 'e.g., Standard contractual clauses, adequacy decision' } }
];

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

const defaultState: WizardState = {
  organization: '',
  sponsor: '',
  strategicObjective: '',
  targetProcess: '',
  currentFriction: '',
  impactedDepartment: '',
  criticalConstraints: '',
  useCaseTitle: '',
  vertical: 'generic',
  dynamicAnswers: {},
  generatedProblem: '',
  generatedSolution: '',
  hypotheses: [],
  recommendations: [],
  bvaConservative: {
    monthlyVolume: '',
    currentMinutes: '',
    targetMinutes: '',
    hourlyCost: '',
    currentErrorRate: '',
    targetErrorRate: '',
    errorCost: '',
    revenueCapacityValue: '',
    annualSolutionCost: '',
    implementationCostOneTime: '',
    implementationCostAnnual: '',
    discountRate: '',
    currency: 'MAD'
  },
  bvaBase: {
    monthlyVolume: '',
    currentMinutes: '',
    targetMinutes: '',
    hourlyCost: '',
    currentErrorRate: '',
    targetErrorRate: '',
    errorCost: '',
    revenueCapacityValue: '',
    annualSolutionCost: '',
    implementationCostOneTime: '',
    implementationCostAnnual: '',
    discountRate: '',
    currency: 'MAD'
  },
  bvaOptimistic: {
    monthlyVolume: '',
    currentMinutes: '',
    targetMinutes: '',
    hourlyCost: '',
    currentErrorRate: '',
    targetErrorRate: '',
    errorCost: '',
    revenueCapacityValue: '',
    annualSolutionCost: '',
    implementationCostOneTime: '',
    implementationCostAnnual: '',
    discountRate: '',
    currency: 'MAD'
  },
  activeBvaScenario: 'base',
  reviewNotes: '',
  // New fields for Kickstart step
  timelineStart: '',
  timelineEnd: '',
  budgetRange: '',
  successMetrics: [],
  stakeholders: [],
  quantifiedPain: '',
  country: 'Pays',
};



const content = {
  fr: {
    title: 'TIFINIA AI Value Studio',
    subtitle: 'Wizard AMOA IA intelligent pour identifier le besoin client, sélectionner le meilleur use case AI et générer un document AMOA + BVA complet.',
    stepTitles: [
      'Kickstart contexte',
      'Questionnaire dynamique',
      'Recommandations & hypothèses',
      'BVA (Business Value Assessment)',
      'Revue & document AMOA'
    ],
    verticalLabel: 'Vertical métier',
    verticals: {
      generic: 'Générique',
      health: 'Santé',
      insurance: 'Assurance / Mutuelle',
      hr: 'RH / Talent',
      public: 'Secteur public',
      finance: 'Finance / Compliance'
    },
    actions: {
      prev: 'Précédent',
      next: 'Continuer',
      save: 'Sauvegarder',
      runKickstart: 'Lancer Kickstart IA',
      inferReco: 'Générer recommandations',
      generateDoc: 'Générer document AMOA + BVA',
      download: 'Télécharger .md'
    },
    notices: {
      saved: 'Brouillon sauvegardé.',
      kickstartDone: 'Brouillon IA généré. Vous pouvez tout éditer avant de continuer.',
      recoDone: 'Recommandations et hypothèses générées.'
    },
    labels: {
      organization: 'Organisation client',
      sponsor: 'Sponsor',
      strategicObjective: 'Objectif stratégique',
      targetProcess: 'Processus cible',
      currentFriction: 'Friction principale',
      impactedDepartment: 'Département impacté',
      criticalConstraints: 'Contraintes critiques',
      useCaseTitle: 'Titre du use case retenu',
      generatedProblem: 'Problem statement proposé',
      generatedSolution: 'Solution IA proposée',
      reviewNotes: 'Notes de revue / décisions',
      // New field labels
      timelineStart: 'Date de début',
      timelineEnd: 'Date de fin',
      budgetRange: 'Budget estimé (MAD)',
      successMetrics: 'Indicateurs de succès (KPIs)',
      stakeholders: 'Parties prenantes clés',
      quantifiedPain: 'Points de douleur quantifiés (temps/coût/performance actuelle)',
      country: 'Pays'
    },
    label: { fr: 'Volume mensuel du processus', en: 'Monthly process process' }
  },
  en: {
    title: 'TIFINIA AI Value Studio',
    subtitle: 'Intelligent AI-advisory wizard to identify client needs, select the best-fit AI use case, and generate a complete AMOA + BVA document.',
    stepTitles: [
      'Context kickstart',
      'Dynamic questionnaire',
      'Recommendations & hypotheses',
      'BVA (Business Value Assessment)',
      'Review & AMOA document'
    ],
    verticalLabel: 'Business vertical',
    verticals: {
      generic: 'Generic',
      health: 'Healthcare',
      insurance: 'Insurance / Mutual',
      hr: 'HR / Talent',
      public: 'Public sector',
      finance: 'Finance / Compliance'
    },
    actions: {
      prev: 'Previous',
      next: 'Continue',
      save: 'Save',
      runKickstart: 'Run AI kickstart',
      inferReco: 'Generate recommendations',
      generateDoc: 'Générer document AMOA + BVA',
      download: 'Download .md'
    },
    notices: {
      saved: 'Draft saved.',
      kickstartDone: 'AI draft generated. You can edit every section before continuing.',
      recoDone: 'Recommendations and hypotheses generated.'
    },
    labels: {
      organization: 'Client organization',
      sponsor: 'Sponsor',
      strategicObjective: 'Strategic objective',
      targetProcess: 'Target process',
      currentFriction: 'Main friction',
      impactedDepartment: 'Impacted department',
      criticalConstraints: 'Contraintes critiques',
      useCaseTitle: 'Selected use-case title',
      generatedProblem: 'Proposed problem statement',
      generatedSolution: 'Proposed AI solution',
      reviewNotes: 'Review notes / décisions',
      // New field labels
      timelineStart: 'Start Date',
      timelineEnd: 'End Date',
      budgetRange: 'Budget Range (MAD)',
      successMetrics: 'Success Metrics (KPIs)',
      stakeholders: 'Key Stakeholders',
      quantifiedPain: 'Quantified Pain Points (time/cost/current performance)',
      country: 'Country'
    },
    label: { fr: 'Volume mensuel du processus', en: 'Monthly process process' }
  }
};
useEffect(() => {
  loadProjects();
}, []);

const coreQuestions: Question[] = [
  {
    id: 'data_availability',
    kind: 'select',
    label: { fr: 'Disponibilité des données', en: 'Data availability' },
    options: [
      { value: 'none', label: { fr: 'Aucune', en: 'None' } },
      { value: 'partial', label: { fr: 'Partielle', en: 'Partial' } },
      { value: 'full', label: { fr: 'Complète', en: 'Full' } }
    ]
  },
  {
    id: 'data_quality',
    kind: 'select',
    label: { fr: 'Qualité des données', en: 'Data quality' },
    options: [
      { value: 'low', label: { fr: 'Faible', en: 'Low' } },
      { value: 'medium', label: { fr: 'Moyenne', en: 'Medium' } },
      { value: 'high', label: { fr: 'Élevée', en: 'High' } }
    ]
  },
  {
    id: 'data_governance',
    kind: 'select',
    label: { fr: 'Gouvernance des données', en: 'Data governance' },
    options: [
      { value: 'none', label: { fr: 'Aucune', en: 'None' } },
      { value: 'basic', label: { fr: 'Basique', en: 'Basic' } },
      { value: 'advanced', label: { fr: 'Avancée', en: 'Advanced' } }
    ]
  },
  {
    id: 'process_detail',
    kind: 'text',
    label: { fr: 'Détail du processus actuel', en: 'Current process detail' },
    placeholder: { fr: 'Decrivez les étapes clés', en: 'Describe key steps' }
  },
  {
    id: 'stakeholder_involvement',
    kind: 'select',
    label: { fr: 'Implication des parties prenantes', en: 'Stakeholder involvement' },
    options: [
      { value: 'low', label: { fr: 'Faible', en: 'Low' } },
      { value: 'medium', label: { fr: 'Moyenne', en: 'Medium' } },
      { value: 'high', label: { fr: 'Élevée', en: 'High' } }
    ]
  },
  {
    id: 'regulatory_constraints',
    kind: 'text',
    label: { fr: 'Contraintes réglementaires applicables', en: 'Applicable regulatory constraints' },
    placeholder: { fr: 'Ex: RGPD, HIPAA', en: 'e.g., GDPR, HIPAA' }
  }
];

    const questions = useMemo(() => {        let qs = [...coreQuestions, ...verticalQuestions[state.vertical]];        if (state.country === 'Maroc') {          qs = [...qs, ...moroccoSpecificQuestions];        }        // Filter based on dynamicAnswers for conditional logic        qs = qs.filter(question => {          if (question.id === 'data_quality' && state.dynamicAnswers['data_availability'] === 'none') {            return false;          }          if (question.id === 'data_governance' && state.dynamicAnswers['data_availability'] === 'none') {            return false;          }          return true;        });        return qs;      }, [state.vertical, state.country, state.dynamicAnswers]);
  const progress = Math.round((step / 4) * 100);

  // Compute active BvaInputs based on active scenario
  const activeBva = useMemo(() => {
    switch (state.activeBvaScenario) {
      case 'conservative': return state.bvaConservative;
      case 'base': return state.bvaBase;
      case 'optimistic': return state.bvaOptimistic;
    }
  }, [state.activeBvaScenario, state.bvaConservative, state.bvaBase, state.bvaOptimistic]);

  const bva = useMemo(() => {
    const annualVolume = toNumber(activeBva.monthlyVolume) * 12;
    const timeSavedHours = Math.max(0, (toNumber(activeBva.currentMinutes) - toNumber(activeBva.targetMinutes)) / 60);
    const annualTimeValue = annualVolume * timeSavedHours * toNumber(activeBva.hourlyCost);
    const errorReduction = Math.max(0, (toNumber(activeBva.currentErrorRate) - toNumber(activeBva.targetErrorRate)) / 100);
    const errorAvoidanceValue = annualVolume * errorReduction * toNumber(activeBva.errorCost);
    const gross = annualTimeValue + errorAvoidanceValue + toNumber(activeBva.revenueCapacityValue);
    const net = gross - toNumber(activeBva.annualSolutionCost);
    return { annualVolume, annualTimeValue, errorAvoidanceValue, gross, net };
  }, [activeBva]);

  const bvaResults = useMemo(() => {
    const scenarios: Array<{
      key: 'conservative' | 'base' | 'optimistic';
      inputs: BvaInputs;
      annualVolume: number;
      annualTimeValue: number;
      errorAvoidanceValue: number;
      gross: number;
      netAnnual: number;
      npv: number;
      paybackYear: number | null;
      sensitivity: {
        npv_timeSavedLow: number;
        npv_timeSavedHigh: number;
        npv_errorReductionLow: number;
        npv_errorReductionHigh: number;
        npv_revenueCapacityLow: number;
        npv_revenueCapacityHigh: number;
      }
    }> = [];

    const scenarioKeys: ('conservative' | 'base' | 'optimistic')[] = ['conservative', 'base', 'optimistic'];
    for (const key of scenarioKeys) {
      let inputs: BvaInputs;
      switch (key) {
        case 'conservative': inputs = state.bvaConservative; break;
        case 'base': inputs = state.bvaBase; break;
        case 'optimistic': inputs = state.bvaOptimistic; break;
      }

      const annualVolume = toNumber(inputs.monthlyVolume) * 12;
      const timeSavedHours = Math.max(0, (toNumber(inputs.currentMinutes) - toNumber(inputs.targetMinutes)) / 60);
      const annualTimeValue = annualVolume * timeSavedHours * toNumber(inputs.hourlyCost);
      const errorReduction = Math.max(0, (toNumber(inputs.currentErrorRate) - toNumber(inputs.targetErrorRate)) / 100);
      const errorAvoidanceValue = annualVolume * errorReduction * toNumber(inputs.errorCost);
      const gross = annualTimeValue + errorAvoidanceValue + toNumber(inputs.revenueCapacityValue);
      const netAnnual = gross - toNumber(inputs.annualSolutionCost) - toNumber(inputs.implementationCostAnnual);
      const implementationCostOneTime = toNumber(inputs.implementationCostOneTime);
      const discountRate = toNumber(inputs.discountRate) / 100; // assuming percentage

      // Cash flows: year0: -implementationCostOneTime, year1-3: netAnnual
      let npv = 0;
      let cumulative = -implementationCostOneTime;
      let paybackYear: number | null = null;
      if (cumulative >= 0) {
        paybackYear = 0;
      }
      for (let year = 1; year <= 3; year++) {
        const discountFactor = Math.pow(1 + discountRate, year);
        const discountedCashFlow = netAnnual / discountFactor;
        npv += discountedCashFlow;
        cumulative += netAnnual;
        if (paybackYear === null && cumulative >= 0) {
          // Fractional payback: year - (previous cumulative / netAnnual)
          const previousCumulative = cumulative - netAnnual;
          paybackYear = (year - 1) + ( -previousCumulative / netAnnual );
        }
      }

      // Sensitivity analysis: vary key drivers by ±20%
      const baseNPV = npv; // we already computed npv above, but we'll recompute for each variation
      // We'll compute sensitivity for each driver
      const sensitivity = {
        npv_timeSavedLow: 0,
        npv_timeSavedHigh: 0,
        npv_errorReductionLow: 0,
        npv_errorReductionHigh: 0,
        npv_revenueCapacityLow: 0,
        npv_revenueCapacityHigh: 0,
      };

      // Helper to compute NPV given modifications
      const computeNPV = (mods: {
        timeSavedHoursMultiplier?: number;
        errorReductionMultiplier?: number;
        revenueCapacityValueMultiplier?: number;
      }) => {
        const modsTimeSavedHours = timeSavedHours * (mods.timeSavedHoursMultiplier ?? 1);
        const modsErrorReduction = errorReduction * (mods.errorReductionMultiplier ?? 1);
        const modsRevenueCapacityValue = toNumber(inputs.revenueCapacityValue) * (mods.revenueCapacityValueMultiplier ?? 1);
        const modsAnnualTimeValue = annualVolume * modsTimeSavedHours * toNumber(inputs.hourlyCost);
        const modsErrorAvoidanceValue = annualVolume * modsErrorReduction * toNumber(inputs.errorCost);
        const modsGross = modsAnnualTimeValue + modsErrorAvoidanceValue + modsRevenueCapacityValue;
        const modsNetAnnual = modsGross - toNumber(inputs.annualSolutionCost) - toNumber(inputs.implementationCostAnnual);
        let modsNPV = -implementationCostOneTime;
        let modsCumulative = -implementationCostOneTime;
        for (let y = 1; y <= 3; y++) {
          const discountFactor = Math.pow(1 + discountRate, y);
          modsNPV += modsNetAnnual / discountFactor;
          modsCumulative += modsNetAnnual;
        }
        return modsNPV;
      };

      sensitivity.npv_timeSavedLow = computeNPV({ timeSavedHoursMultiplier: 0.8 });
      sensitivity.npv_timeSavedHigh = computeNPV({ timeSavedHoursMultiplier: 1.2 });
      sensitivity.npv_errorReductionLow = computeNPV({ errorReductionMultiplier: 0.8 });
      sensitivity.npv_errorReductionHigh = computeNPV({ errorReductionMultiplier: 1.2 });
      sensitivity.npv_revenueCapacityLow = computeNPV({ revenueCapacityValueMultiplier: 0.8 });
      sensitivity.npv_revenueCapacityHigh = computeNPV({ revenueCapacityValueMultiplier: 1.2 });

      scenarios.push({
        key,
        inputs,
        annualVolume,
        annualTimeValue,
        errorAvoidanceValue,
        gross,
        netAnnual,
        npv,
        paybackYear,
        sensitivity,
      });
    }

    return scenarios;
  }, [state.bvaConservative, state.bvaBase, state.bvaOptimistic]);

  const runKickstart = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/kickstart`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          organization: state.organization,
          target_process: state.targetProcess,
          current_friction: state.currentFriction,
          impacted_department: state.impactedDepartment,
        }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const result = await response.json();
      setState(prev => ({
        ...prev,
        generatedProblem: result.problem_statement,
        generatedSolution: result.proposed_solution,
      }));
      setNotice(t.notices.kickstartDone);
    } catch (err) {
      console.error('Failed to load project history:', err);
      setNotice('Erreur lors du chargement de l\'historique du projet.');
      // Fallback to step 0
      setStep(0);
      setState(prev => ({ ...prev, project_id: projectId }));
    }
    if (impact === 'high' || impact === 'critical') {
      recos.push(
        lang === 'fr'
          ? 'Forcer un contrôle humain sur les décisions à impact et tracer les justifications.'
          : 'Enforce human review on high-impact decisions and log justifications.'
      );
    }

if (human === 'mandatory') {
  recos.push(
    lang === 'fr'
      ? 'Concevoir un workflow HITL avec leurs seus d\'escalade explicites.'
      : 'Design a HITL workflow with explicit escalation thresholds.'
  );
}
    doc += '## 6. Dynamic Questionnaire Responses\n\n';
    doc += dynamicSections + '\n\n';
    doc += '## 7. Recommendations & Hypotheses\n\n';
    doc += recommendationsSection + '\n\n';
    doc += '## 8. Conclusion\n\n';
    doc += 'Based on the assessment, the proposed AI use case demonstrates potential value and feasibility. Next steps include detailed planning, resource allocation, and stakeholder engagement.\n\n';
    doc += '---\n\n';
    doc += '*Generated on ' + date + '*\n';
    return doc;
  };



  const downloadDocument = () => {
    if (!finalDoc) return;
    const blob = new Blob([finalDoc], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = lang === 'fr' ? 'amoa_bva_fr.md' : 'amoa_bva_en.md';
    a.click();
    URL.revokeObjectURL(url);
  };



  const setAnswer = (id: string, value: string) => {
    setState(prev => ({ ...prev, dynamicAnswers: { ...prev.dynamicAnswers, [id]: value } }));
    setNotice('');
  };



  const setBvaField = (key: keyof BvaInputs, value: string) => {
    setState(prev => {
      const newState = { ...prev };
      switch (prev.activeBvaScenario) {
        case 'conservative':
          newState.bvaConservative = { ...prev.bvaConservative, [key]: value };
          break;
        case 'base':
          newState.bvaBase = { ...prev.bvaBase, [key]: value };
          break;
        case 'optimistic':
          newState.bvaOptimistic = { ...prev.bvaOptimistic, [key]: value };
          break;
      }
      return newState;
    });
    setNotice('');
  };



  const setActiveBvaScenario = (scenario: 'conservative' | 'base' | 'optimistic') => {
    setState(prev => ({ ...prev, activeBvaScenario: scenario }));
    setNotice('');
  };



  const saveWizardStep = async () => {
    if (!selectedProjectId) return;
    setLoading(true);
    try {
      await fetch(`${API_BASE_URL}/api/wizard/save/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: selectedProjectId,
          step: step,
          state: state,
        }),
      });
      setNotice(t.notices.saved);
    } catch (err) {
      console.error('Failed to save wizard step:', err);
      setNotice('Erreur lors de la sauvegarde. Veuillez réessayer.');
    } finally {
      setLoading(false);
    }
  };



  const loadWizardStep = async (projectId: string, stepNum: number) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/wizard/load/${projectId}/${stepNum}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: {step: number; state: WizardState} = await res.json();
      setState(prev => ({ ...prev, ...data.state }));
      setStep(data.step);
      setSelectedProjectId(projectId);
    } catch (err) {
      console.error('Failed to load wizard step:', err);
      setNotice('Erreur lors du chargement. Veuillez réessayer.');
    } finally {
      setLoading(false);
    }
  };



  const handleProjectSelect = async (projectId: string | null) => {
    if (projectId === null) {
      // New project
      setSelectedProjectId(null);
      setState(defaultState);
      setStep(0);
      return;
    }
    setSelectedProjectId(projectId);
    // Load the highest saved step for this project
    try {
      const historyRes = await fetch(`${API_BASE_URL}/api/wizard/history/${projectId}`);
      if (!historyRes.ok) throw new Error(`HTTP ${historyRes.status}`);
      const history: Array<{step: number; saved_at: string}> = await historyRes.json();
      if (history.length === 0) {
        // No saved steps, start at step 0
        setStep(0);
        setState(prev => ({ ...prev, project_id: projectId }));
        return;
      }
      const latest = history.reduce((max, cur) => (cur.step > max.step ? cur : max));
      await loadWizardStep(projectId, latest.step);
      setNotice('Erreur lors du chargement de l\'historique du projet.');



  const StepKickstart = () => (
    <div className="space-y-4">\n      <h2 className="text-xl font-bold">{t.stepTitles[0]}</h2>\n      {field(t.labels.organization, state.organization, (v) => setState((p) => ({ ...p, organization: v })))}
      {field(t.labels.sponsor, state.sponsor, (v) => setState((p) => ({ ...p, sponsor: v })))}
      {field(t.labels.strategicObjective, state.strategicObjective, (v) => setState((p) => ({ ...p, strategicObjective: v })))}
      {field(t.labels.targetProcess, state.targetProcess, (v) => setState((p) => ({ ...p, targetProcess: v })))}
      {field(t.labels.currentFriction, state.currentFriction, (v) => setState((p) => ({ ...p, currentFriction: v })))}
      {field(t.labels.impactedDepartment, state.impactedDepartment, (v) => setState((p) => ({ ...p, impactedDepartment: v })))}
      {field(t.labels.criticalConstraints, state.criticalConstraints, (v) => setState((p) => ({ ...p, criticalConstraints: v })))}
      {field(t.labels.useCaseTitle, state.useCaseTitle, (v) => setState((p) => ({ ...p, useCaseTitle: v })))}
      {field(t.labels.timelineStart, state.timelineStart, (v) => setState((p) => ({ ...p, timelineStart: v })), undefined, 'date')}
      {field(t.labels.timelineEnd, state.timelineEnd, (v) => setState((p) => ({ ...p, timelineEnd: v })), undefined, 'date')}
      {field(t.labels.budgetRange, state.budgetRange, (v) => setState((p) => ({ ...p, budgetRange: v })))}
      <textareaField
        label={t.labels.successMetrics}
        value={state.successMetrics.join('\\n')}
        onChange={(v) => setState(p => ({
          ...p,
          successMetrics: v
            .split('\\n')
            .map(line => line.trim())
            .filter(line => line.length > 0)
        }))}
      />
        <label className="block space-y-2">
          <span className="text-sm font-medium text-slate-700">{t.verticalLabel}</span>
          <select
            value={state.vertical}
            onChange={(e) => setState((p) => ({ ...p, vertical: e.target.value as Vertical }))}
            className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            {(Object.keys(t.verticals) as Vertical[]).map((v) => (
              <option key={v} value={v}>
                {t.verticals[v]}
              </option>
            ))}
          </select>
        </label>
        <select
          value={state.country}
          onChange={(e) => setState((p) => ({ ...p, country: e.target.value }))}
          className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
        >
          <option value="">--</option>
          <option value="Union européenne">Union européenne</option>
          <option value="Maroc">Maroc</option>
          <option value="Canada">Canada</option>
        </select>
        {field(t.labels.country, state.country, (v) => setState((p) => ({ ...p, country: v })))}
      <button
        onClick={runKickstart}
        disabled={loading}
        className={`rounded-xl ${loading ? "bg-slate-500" : "bg-black"} px-4 py-2 text-sm text-white`}
      >
        {t.actions.runKickstart}
      </button>

      {field(t.labels.generatedProblem, state.generatedProblem, (v) => setState((p) => ({ ...p, generatedProblem: v })))}
      {field(t.labels.generatedSolution, state.generatedSolution, (v) => setState((p) => ({ ...p, generatedSolution: v })))}
    </div>
  );

  const StepQuestionnaire = () => (
    <div className="space-y-4">\n      <h2 className=\"text-xl font-bold\">{t.stepTitles[1]}</h2>
      <div className=\"grid gap-4 md:grid-cols-2\">
        {questions.map((q) =>
          field(
            q.label[lang],
            state.dynamicAnswers[q.id] || \"\",
            (v) => setAnswer(q.id, v),
            q.options?.map((o) => ({ value: o.value, label: o.label[lang] })),
            q.kind,
            q.placeholder?.[lang],
          ),
        )}
      </div>
    </div>
  );

  const StepRecommendations = () => (
    <div className=\"space-y-4\">
      <h2 className=\"text-xl font-bold\">{t.stepTitles[2]}</h2>
      <div className=\"space-y-4\">
        <button
          onClick={inferRecommendations}
          disabled={loading}
          className={`rounded-xl ${loading ? \"bg-slate-500\" : \"bg-indigo-600\"} px-4 py-2 text-sm text-white`}
        >
          {t.actions.inferReco}
        </button>

        <div className=\"grid gap-4 md:grid-cols-2\">
          <div className=\"rounded-xl border border-slate-200 p-4\">
            <h3 className=\"font-semibold\">{lang === \"fr\" ? \"Recommandations\" : \"Recommendations\"}</h3>
            <ul className=\"mt-2 list-disc space-y-1 pl-5 text-sm\">
              {(state.recommendations.length ? state.recommendations : [\"-\"]).map((r, idx) => (
                <li key={idx}>{r}</li>
              ))}
            </ul>
          </div>

          <div className=\"rounded-xl border border-slate-200 p-4\">
            <h3 className=\"font-semibold\">{lang === \"fr\" ? \"Hypothèses\" : \"Hypotheses\"}</h3>
            <ul className=\"mt-2 list-disc space-y-1 pl-5 text-sm\">
              {(state.hypotheses.length ? state.hypotheses : [\"-\"]).map((h, idx) => (
                <li key={idx}>{h}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );

  const StepBVA = () => (
    <div className=\"space-y-4\">
      <h2 className=\"text-xl font-bold\">{t.stepTitles[3]}</h2>
      <div className=\"space-y-4\">
        {/* Scenario selector */}
        <div className=\"rounded-xl border border-slate-200 p-4\">
          <h3 className=\"font-semibold\">{lang === \"fr\" ? \"Scénario\" : \"Scenario\"}</h3>
          <div className=\"mt-2 space-y-2\">
            <label className=\"flex items-center space-x-2\">
              <input
                type=\"radio\"
                value=\"conservative\"
                checked={activeBvaScenario === 'conservative'}
                onChange={() => setActiveBvaScenario('conservative')}
                className=\"h-4 w-4 text-indigo-600\"
              />
              <span>{lang === \"fr\" ? \"Conservateur\" : \"Conservative\"}</span>
            </label>
            <label className=\"flex items-center space-x-2\">
              <input
                type=\"radio\"
                value=\"base\"
                checked={activeBvaScenario === 'base'}
                onChange={() => setActiveBvaScenario('base')}
                className=\"h-4 w-4 text-indigo-600\"
              />
              <span>{lang === \"fr\" ? \"Base\" : \"Base\"}</span>
            </label>
            <label className=\"flex items-center space-x-2\">
              <input
                type=\"radio\"
                value=\"optimistic\"
                checked={activeBvaScenario === 'optimistic'}
                onChange={() => setActiveBvaScenario('optimistic')}
                className=\"h-4 w-4 text-indigo-600\"
              />
              <span>{lang === \"fr\" ? \"Optimiste\" : \"Optimistic\"}</span>
            </label>
          </div>
        </div>

        {/* Input fields for active scenario */}
        <div className=\"grid gap-4 md:grid-cols-3\">
          {field(lang === \"fr\" ? \"Volume mensuel\" : \"Monthly volume\", 
            activeBvaScenario === 'conservative' ? state.bvaConservative.monthlyVolume :
            activeBvaScenario === 'base' ? state.bvaBase.monthlyVolume : state.bvaOptimistic.monthlyVolume,
            (v) => setBvaField('monthlyVolume', v), undefined, \"number\")}
          {field(lang === \"fr\" ? \"Temps actuel (min)\" : \"Current time (min)\", 
            activeBvaScenario === 'conservative' ? state.bvaConservative.currentMinutes :
            activeBvaScenario === 'base' ? state.bvaBase.currentMinutes : state.bvaOptimistic.currentMinutes,
            (v) => setBvaField('currentMinutes', v), undefined, \"number\")}
          {field(lang === \"fr\" ? \"Temps cible (min)\" : \"Target time (min)\", 
            activeBvaScenario === 'conservative' ? state.bvaConservative.targetMinutes :
            activeBvaScenario === 'base' ? state.bvaBase.targetMinutes : state.bvaOptimistic.targetMinutes,
            (v) => setBvaField('targetMinutes', v), undefined, \"number\")}
          {field(lang === \"fr\" ? \"Coût horaire (MAD)\" : \"Hourly cost (MAD)\" ,
            activeBvaScenario === 'conservative' ? state.bvaConservative.hourlyCost :
            activeBvaScenario === 'base' ? state.bvaBase.hourlyCost : state.bvaOptimistic.hourlyCost,
            (v) => setBvaField('hourlyCost', v), undefined, \"number\")}
          {field(lang === \"fr\" ? \"Taux erreur actuel (%)\" : \"Current error rate (%)\", 
            activeBvaScenario === 'conservative' ? state.bvaConservative.currentErrorRate :
            activeBvaScenario === 'base' ? state.bvaBase.currentErrorRate : state.bvaOptimistic.currentErrorRate,
            (v) => setBvaField('currentErrorRate', v), undefined, \"number\")}
          {field(lang === \"fr\" ? \"Taux erreur cible (%)\" : \"Target error rate (%)\", 
            activeBvaScenario === 'conservative' ? state.bvaConservative.targetErrorRate :
            activeBvaScenario === 'base' ? state.bvaBase.targetErrorRate : state.bvaOptimistic.targetErrorRate,
            (v) => setBvaField('targetErrorRate', v), undefined, \"number\")}
          {field(lang === \"fr\" ? \"Coût par erreur\" : \"Cost per error\", 
            activeBvaScenario === 'conservative' ? state.bvaConservative.errorCost :
            activeBvaScenario === 'base' ? state.bvaBase.errorCost : state.bvaOptimistic.errorCost,
            (v) => setBvaField('errorCost', v), undefined, \"number\")}
          {field(lang === \"fr\" ? \"Valeur capacité/revenu\" : \"Revenue/capacity value\", 
            activeBvaScenario === 'conservative' ? state.bvaConservative.revenueCapacityValue :
            activeBvaScenario === 'base' ? state.bvaBase.revenueCapacityValue : state.bvaOptimistic.revenueCapacityValue,
            (v) => setBvaField('revenueCapacityValue', v), undefined, \"number\")}
          {field(lang === \"fr\" ? \"Coût annuel solution\" : \"Annual solution cost\", 
            activeBvaScenario === 'conservative' ? state.bvaConservative.annualSolutionCost :
            activeBvaScenario === 'base' ? state.bvaBase.annualSolutionCost : state.bvaOptimistic.annualSolutionCost,
            (v) => setBvaField('annualSolutionCost', v), undefined, \"number\")}
          {field(lang === \"fr\" ? \"Coût d'implémentation unique\" : \"One-time implementation cost\", 
            activeBvaScenario === 'conservative' ? state.bvaConservative.implementationCostOneTime :
            activeBvaScenario === 'base' ? state.bvaBase.implementationCostOneTime : state.bvaOptimistic.implementationCostOneTime,
            (v) => setBvaField('implementationCostOneTime', v), undefined, \"number\")}
          {field(lang === \"fr\" ? \"Coût d'implémentation annuel\" : \"Annual implementation cost\", 
            activeBvaScenario === 'conservative' ? state.bvaConservative.implementationCostAnnual :
            activeBvaScenario === 'base' ? state.bvaBase.implementationCostAnnual : state.bvaOptimistic.implementationCostAnnual,
            (v) => setBvaField('implementationCostAnnual', v), undefined, \"number\")}
          {field(lang === \"fr\" ? \"Taux d'actualisation (%)\" : \"Discount rate (%)\", 
            activeBvaScenario === 'conservative' ? state.bvaConservative.discountRate :
            activeBvaScenario === 'base' ? state.bvaBase.discountRate : state.bvaOptimistic.discountRate,
            (v) => setBvaField('discountRate', v), undefined, \"number\")}
        </div>

        {/* Active scenario results */}
        <div className=\"rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm\">
          <p>- Annual Volume: {bva.annualVolume.toFixed(0)}</p>
          <p>- Annual Time Value: {bva.annualTimeValue.toFixed(2)}</p>
          <p>- Error Avoidance Value: {bva.errorAvoidanceValue.toFixed(2)}</p>
          <p>- Estimated Gross Value: {bva.gross.toFixed(2)}</p>
          <p>- Estimated Net Value (Annual): {bva.net.toFixed(2)}</p>
        </div>

        {/* Scenario comparison table */}
        <div className=\"rounded-xl border border-slate-200 p-4\">
          <h3 className=\"font-semibold mb-2\">{lang === \"fr\" ? \"Comparaison des scénarios\" : \"Scenario Comparison\"}</h3>
          <table className=\"w-full text-sm\">
            <thead className=\"border-b\">\n              <tr>\n                <th className=\"text-left p-2\">{lang === \"fr\" ? \"Scénario\" : \"Scenario\"}</th>\n                <th className=\"text-left p-2\">NPV (3 ans)</th>\n                <th className=\"text-left p-2\">Payback (années)</th>\n                <th className=\"text-left p-2\">Valeur nette annuelle</th>\n              </tr>\n            </thead>\n            <tbody>\n              {bvaResults.map((sc) => (\n                <tr key={sc.key} className=\"border-t\">\n                  <td className=\"p-2\">{sc.key === 'conservative' ? (lang === \"fr\" ? \"Conservateur\" : \"Conservative\") : sc.key === 'base' ? (lang === \"fr\" ? \"Base\" : \"Base\") : (lang === \"fr\" ? \"Optimiste\" : \"Optimistic\")}</td>\n                  <td className=\"p-2\">{sc.npv.toFixed(0)}</td>\n                  <td className=\"p-2\">{sc.paybackYear !== null ? sc.paybackYear.toFixed(1) : \">3\"}</td>\n                  <td className=\"p-2\">{sc.netAnnual.toFixed(0)}</td>\n                </tr>\n              ))}\n            </tbody>\n          </table>\n        </div>\n\n        {/* Sensitivity analysis table */}\n        <div className=\"rounded-xl border border-slate-200 p-4 mt-4\">\n          <h3 className=\"font-semibold mb-2\">{lang === \"fr\" ? \"Analyse de sensibilité (±20%)\" : \"Sensitivity Analysis (±20%)\"}</h3>\n          <p className=\"mb-2 text-xs text-slate-500\">{lang === \"fr\" ? \"Impact sur le NPV lorsque les facteurs clés varient de ±20%\" : \"Impact on NPV when key drivers vary by ±20%\"}</p>\n          <table className=\"w-full text-xs\">\n            <thead className=\"border-b\">\n              <tr>\n                <th className=\"text-left p-2\">{lang === \"fr\" ? \"Facteur\" : \"Factor\"}</th>\n                <th className=\"text-left p-2\">-20%</th>\n                <th className=\"text-left p-2\">+20%</th>\n              </tr>\n            </thead>\n            <tbody>\n              {bvaResults.map((sc) => (\n                <>\n                  <tr key={`${sc.key}-time-saved`} className=\"border-b\">\n                    <td className=\"p-2 font-medium\">{lang === \"fr\" ? \"Temps sauvegardé\" : \"Time Saved\"}</td>\n                    <td className=\"p-2\">{sc.sensitivity.npv_timeSavedLow.toFixed(0)}</td>\n                    <td className=\"p-2\">{sc.sensitivity.npv_timeSavedHigh.toFixed(0)}</td>\n                  </tr>\n                  <tr key={`${sc.key}-error-reduction`} className=\"border-b\">\n                    <td className=\"p-2 font-medium\">{lang === \"fr\" ? \"Réduction d'erreurs\" : \"Error Reduction\"}</td>\n                    <td className=\"p-2\">{sc.sensitivity.npv_errorReductionLow.toFixed(0)}</td>\n                    <td className=\"p-2\">{sc.sensitivity.npv_errorReductionHigh.toFixed(0)}</td>\n                  </tr>\n                  <tr key={`${sc.key}-revenue-capacity`}>\n                    <td className=\"p-2 font-medium\">{lang === \"fr\" ? \"Valeur capacité/revenu\" : \"Revenue/Capacity Value\"}</td>\n                    <td className=\"p-2\">{sc.sensitivity.npv_revenueCapacityLow.toFixed(0)}</td>\n                    <td className=\"p-2\">{sc.sensitivity.npv_revenueCapacityHigh.toFixed(0)}</td>\n                  </tr>\n                </>\n              ))}\n            </tbody>\n          </table>\n        </div>\n      </div>\n    </div>\n  );\n\n  const StepReview = () => (\n    <div className=\"space-y-4\">\n      <h2 className=\"text-xl font-bold\">{t.stepTitles[4]}</h2>\n      {field(t.labels.reviewNotes, state.reviewNotes, (v) => setState((p) => ({ ...p, reviewNotes: v })))}\n      <div className=\"space-y-4\">\n        <button\n          onClick={generateFinalDocument}\n          disabled={loading}\n          className={`rounded-xl ${loading ? \"bg-slate-500\" : \"bg-indigo-600\"} px-4 py-2 text-sm text-white`}\n        >\n          {t.actions.generateDoc}\n        </button>\n\n        {finalDoc ? (\n          <div className=\"space-y-2\">\n            <pre className=\"max-h-96 overflow-auto rounded-xl border border-slate-200 bg-white p-3 text-xs\">\n              {finalDoc}\n            </pre>\n            <button\n              onClick={downloadDocument}\n              className=\"rounded-xl border border-slate-300 px-4 py-2 text-sm\"
            >\n              {t.actions.download}\n            </button>\n          </div>\n        ) : null}\n      </div>\n    </div>\n  );\n\n  return (\n    <main className=\"min-h-screen bg-slate-50 p-6 md:p-10\">\n      <div className=\"mx-auto max-w-5xl space-y-6\">\n        <header className=\"rounded-2xl bg-white p-6 shadow-sm ring-1 ring-black/5\">\n          <div className=\"flex flex-wrap items-center justify-between gap-3\">\n            <div>\n              <h1 className=\"text-2xl font-bold\">{t.title}</h1>\n              <p className=\"mt-1 text-sm text-slate-600\">{t.subtitle}</p>\n            </div>\n            <div className=\"flex rounded-xl border border-black/10 p-1\">\n              <button\n                className={`rounded-lg px-3 py-1 text-sm ${lang === \"fr\" ? \"bg-black text-white\" : \"text-black\"}`}\n                onClick={() => setLang(\"fr\")}\n              >\n                FR\n              </button>\n              <button\n                className={`rounded-lg px-3 py-1 text-sm ${lang === \"en\" ? \"bg-black text-white\" : \"text-black\"}`}\n                onClick={() => setLang(\"en\")}\n              >\n                EN\n              </button>\n            </div>\n          </div>\n\n          <div className=\"mt-4\">\n            <div className=\"mb-2 flex items-center justify-between text-xs text-slate-500\">\n              <span>Projet :</span>\n              <select\n                value={selectedProjectId ?? \"\"}\n                onChange={(e) => handleProjectSelect(e.target.value === \"\" ? null : e.target.value)}\n                className=\"rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm\"
              >\n                <option value=\"\">-- Nouveau projet --</option>\n                {projects.map(p => (\n                  <option key={p.id} value={p.id}>\n                    {p.title}\n                  </option>\n                ))}\n              </select>\n            </div>\n            <div className=\"h-2 rounded-full bg-slate-200\">\n              <div className={step === 0 ? \"h-2 rounded-full bg-indigo-600\" : \"h-2 rounded-full bg-slate-200\"} style={{ width: `${progress}%` }} />\n            </div>\n          </div>\n        </header>\n\n        <section className=\"rounded-2xl bg-white p-6 shadow-sm ring-1 ring-black/5 space-y-5\">\n          <StepKickstart />\n          <StepQuestionnaire />\n          <StepRecommendations />\n          <StepBVA />\n          <StepReview />\n          <div className=\"flex flex-wrap items-center gap-2 pt-2\">\n            <button\n              onClick={() => setStep((s) => Math.max(0, s - 1))}\n              disabled={loading || step === 0}\n              className={`rounded-xl border border-slate-300 px-4 py-2 text-sm ${loading ? \"opacity-50\" : \"\"}`}\n            >\n              {t.actions.prev}\n            </button>\n            <button\n              onClick={saveWizardStep}\n              disabled={loading || !selectedProjectId}\n              className={`rounded-xl border border-slate-300 px-4 py-2 text-sm ${loading || !selectedProjectId ? \"opacity-50\" : \"\"}`}\n            >\n              {t.actions.save}\n            </button>\n            <button\n              onClick={() => setStep((s) => Math.min(4, s + 1))}\n              disabled={loading || step === 4}\n              className={`rounded-xl ${loading ? \"bg-slate-500\" : \"bg-black\"} px-4 py-2 text-sm text-white`}\n            >\n              {t.actions.next}\n            </button>\n          </div>\n\n          {notice ? <p className=\"text-sm text-emerald-700\">{notice}</p> : null}\n        </section>\n      </div>\n    </main>\n  );\n}