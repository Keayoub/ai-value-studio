export type Locale = "fr" | "en";

export type WizardCopy = {
  loading: string;
  unavailableTitle: string;
  unavailableDescription: string;
  createDraft: string;
  newDraft: string;
  loadingError: string;
  networkError: string;
  retry: string;
  autosaveSaving: string;
  autosaveSaved: string;
  autosaveFailed: string;
  progress: string;
  optional: string;
  unavailableChip: string;
  readOnly: string;
  interviewMode: string;
  interviewBanner: string;
  interviewHelp: string;
  respondent: string;
  respondentMissing: string;
  confirmRespondent: string;
  previous: string;
  continue: string;
  submit: string;
  review: string;
  reviewDescription: string;
  missingInformation: string;
  recommendation: string;
  sponsor: string;
  facts: string;
  derivedValue: string;
  grossValue: string;
  riskProfile: string;
  noValuePreview: string;
  noData: string;
  editStep: string;
  editAnswer: string;
  yes: string;
  no: string;
  currentStep: string;
  kickstartTitle: string;
  kickstartDescription: string;
  kickstartReadyDescription: string;
  kickstartDisabledExplanation: string;
  kickstartUnavailableExplanation: string;
  kickstartConsultantOnlyExplanation: string;
  kickstartDraftOnlyExplanation: string;
  kickstartGenerate: string;
  kickstartGenerating: string;
  kickstartGeneratedAt: string;
  kickstartNoProposal: string;
  kickstartCurrentAnswer: string;
  kickstartProposal: string;
  kickstartAccept: string;
  kickstartIgnore: string;
  kickstartIgnored: string;
  kickstartReviewAgain: string;
  kickstartApplied: string;
  kickstartOverwriteTitle: string;
  kickstartOverwriteDescription: string;
  kickstartConfirmOverwrite: string;
  kickstartCancelOverwrite: string;
  kickstartNoAnswer: string;
  kickstartKpiHint: string;
  kickstartProblemStatement: string;
  kickstartAiSolution: string;
  kickstartKpiProposals: string;
  kickstartValueHypotheses: string;
  kickstartRisks: string;
  kickstartMissingInfoTitle: string;
  recommendationSummary: string;
  submittedVersion: string;
  questionRequired: string;
  saveDraft: string;
  requestInformation: string;
  requestInformationUnavailable: string;
  stepCurrent: string;
  stepComplete: string;
  stepPending: string;
  chooseOption: string;
  aiAssisted: string;
  currencySuffix: string;
  validationSummaryTitle: string;
  validationSummaryDescription: string;
};

export const wizardCopy: Record<Locale, WizardCopy> = {
  fr: {
    loading: "Chargement de l’évaluation…",
    unavailableTitle: "Aucune évaluation disponible",
    unavailableDescription:
      "Créez un brouillon d’évaluation pour commencer le parcours en huit étapes.",
    createDraft: "Créer un brouillon d’évaluation",
    newDraft: "Créer une nouvelle version brouillon",
    loadingError: "Nous n’avons pas pu charger cette évaluation.",
    networkError: "Enregistrement impossible. Réessayer",
    retry: "Réessayer",
    autosaveSaving: "Enregistrement…",
    autosaveSaved: "Enregistré à",
    autosaveFailed: "Enregistrement impossible.",
    progress: "Étape",
    optional: "Optionnel",
    unavailableChip: "Indisponible",
    readOnly: "Lecture seule",
    interviewMode: "Mode entretien",
    interviewBanner: "Mode entretien actif — vos réponses sont enregistrées au nom de",
    interviewHelp:
      "Confirmez le répondant avant de saisir des réponses au nom d’une autre personne.",
    respondent: "Répondant",
    respondentMissing: "Confirmez le répondant pour activer le mode entretien.",
    confirmRespondent:
      "Changer le répondant mettra à jour les prochaines réponses capturées. Continuer ?",
    previous: "Précédent",
    continue: "Continuer",
    submit: "Soumettre pour revue",
    review: "Revue avant soumission",
    reviewDescription:
      "Synthèse immuable des réponses actuelles, des informations manquantes et de la recommandation.",
    missingInformation: "Informations manquantes",
    recommendation: "Recommandation",
    sponsor: "Sponsor",
    facts: "Faits saisis",
    derivedValue: "Aperçu déterministe de valeur",
    grossValue: "Valeur brute",
    riskProfile: "Profil de risque",
    noValuePreview: "Renseignez les entrées de valeur pour calculer l’aperçu déterministe.",
    noData: "Aucune donnée",
    editStep: "Modifier l’étape",
    editAnswer: "Modifier",
    yes: "Oui",
    no: "Non",
    currentStep: "Étape en cours",
    kickstartTitle: "Kickstart IA",
    kickstartDescription:
      "Préparez une proposition IA éditable sans modifier automatiquement les réponses existantes.",
    kickstartReadyDescription:
      "Générez une proposition puis acceptez, modifiez ou ignorez chaque champ avant tout enregistrement.",
    kickstartDisabledExplanation:
      "L’assistance IA est désactivée pour cet espace. Un administrateur doit l’activer avant toute génération.",
    kickstartUnavailableExplanation:
      "L’assistance IA est activée pour cet espace, mais aucun fournisseur n’est configuré côté serveur pour le moment.",
    kickstartConsultantOnlyExplanation:
      "La génération de proposition IA est réservée au consultant affecté à cette version.",
    kickstartDraftOnlyExplanation:
      "La génération de proposition IA n’est disponible que sur la version brouillon en cours.",
    kickstartGenerate: "Générer une proposition IA",
    kickstartGenerating: "Génération de la proposition IA…",
    kickstartGeneratedAt: "Proposition générée à",
    kickstartNoProposal:
      "Aucune proposition générée pour le moment. Les réponses existantes restent inchangées jusqu’à acceptation explicite.",
    kickstartCurrentAnswer: "Réponse actuelle",
    kickstartProposal: "Proposition IA éditable",
    kickstartAccept: "Accepter cette proposition",
    kickstartIgnore: "Ignorer",
    kickstartIgnored: "Proposition ignorée pour ce champ.",
    kickstartReviewAgain: "Réexaminer la proposition",
    kickstartApplied: "Suggestion enregistrée comme réponse assistée par IA.",
    kickstartOverwriteTitle: "Confirmer le remplacement de la réponse actuelle",
    kickstartOverwriteDescription:
      "Cette action remplacera la réponse existante par une suggestion assistée par IA pour ce champ uniquement.",
    kickstartConfirmOverwrite: "Confirmer le remplacement",
    kickstartCancelOverwrite: "Annuler",
    kickstartNoAnswer: "Aucune réponse enregistrée",
    kickstartKpiHint:
      "Les propositions seront enregistrées dans le champ KPI principal sous forme d’une liste séparée par des points-virgules.",
    kickstartProblemStatement: "Problème",
    kickstartAiSolution: "Solution IA",
    kickstartKpiProposals: "Propositions de KPI",
    kickstartValueHypotheses: "Hypothèses de valeur",
    kickstartRisks: "Risques",
    kickstartMissingInfoTitle: "Informations manquantes",
    recommendationSummary: "Résumé de la recommandation",
    submittedVersion: "Version soumise",
    questionRequired: "obligatoire",
    saveDraft: "Enregistrer le brouillon",
    requestInformation: "Demander des informations",
    requestInformationUnavailable:
      "Cette action reste indisponible tant qu’aucune API autorisée ne peut enregistrer une demande d’informations.",
    stepCurrent: "En cours",
    stepComplete: "Complète",
    stepPending: "À compléter",
    chooseOption: "Choisir…",
    aiAssisted: "Assisté par IA",
    currencySuffix: "EUR",
    validationSummaryTitle: "Corrigez les champs suivants avant de continuer",
    validationSummaryDescription:
      "Chaque lien replace le focus sur le champ concerné.",
  },
  en: {
    loading: "Loading assessment…",
    unavailableTitle: "No assessment available",
    unavailableDescription: "Create a draft assessment to start the eight-step flow.",
    createDraft: "Create draft assessment",
    newDraft: "Create new draft version",
    loadingError: "We could not load this assessment.",
    networkError: "Saving failed. Retry",
    retry: "Retry",
    autosaveSaving: "Saving…",
    autosaveSaved: "Saved at",
    autosaveFailed: "Saving failed.",
    progress: "Step",
    optional: "Optional",
    unavailableChip: "Unavailable",
    readOnly: "Read only",
    interviewMode: "Interview mode",
    interviewBanner: "Interview mode active — your answers are being captured for",
    interviewHelp: "Confirm the respondent before capturing answers on someone else’s behalf.",
    respondent: "Respondent",
    respondentMissing: "Confirm the respondent to enable interview mode.",
    confirmRespondent:
      "Changing the respondent will affect the next captured answers. Continue?",
    previous: "Previous",
    continue: "Continue",
    submit: "Submit for review",
    review: "Review before submission",
    reviewDescription:
      "Immutable summary of the current answers, missing information, and recommendation.",
    missingInformation: "Missing information",
    recommendation: "Recommendation",
    sponsor: "Sponsor",
    facts: "Entered facts",
    derivedValue: "Deterministic value preview",
    grossValue: "Gross value",
    riskProfile: "Risk profile",
    noValuePreview: "Complete the value inputs to compute the deterministic preview.",
    noData: "No data",
    editStep: "Edit step",
    editAnswer: "Edit",
    yes: "Yes",
    no: "No",
    currentStep: "Current step",
    kickstartTitle: "AI kickstart",
    kickstartDescription:
      "Prepare an editable AI proposal without automatically changing existing answers.",
    kickstartReadyDescription:
      "Generate a proposal, then accept, edit, or ignore each field before anything is saved.",
    kickstartDisabledExplanation:
      "AI assistance is disabled for this workspace. An administrator must enable it before generation is allowed.",
    kickstartUnavailableExplanation:
      "AI assistance is enabled for this workspace, but no server-side provider is configured right now.",
    kickstartConsultantOnlyExplanation:
      "AI proposal generation is limited to the consultant assigned to this draft.",
    kickstartDraftOnlyExplanation:
      "AI proposal generation is available only for the current draft assessment version.",
    kickstartGenerate: "Generate AI proposal",
    kickstartGenerating: "Generating AI proposal…",
    kickstartGeneratedAt: "Proposal generated at",
    kickstartNoProposal:
      "No proposal has been generated yet. Existing answers stay unchanged until you explicitly accept a field.",
    kickstartCurrentAnswer: "Current answer",
    kickstartProposal: "Editable AI proposal",
    kickstartAccept: "Accept this proposal",
    kickstartIgnore: "Ignore",
    kickstartIgnored: "Proposal ignored for this field.",
    kickstartReviewAgain: "Review the proposal again",
    kickstartApplied: "Suggestion saved as an AI-assisted answer.",
    kickstartOverwriteTitle: "Confirm replacing the current answer",
    kickstartOverwriteDescription:
      "This replaces the existing answer with an AI-assisted suggestion for this field only.",
    kickstartConfirmOverwrite: "Confirm replacement",
    kickstartCancelOverwrite: "Cancel",
    kickstartNoAnswer: "No saved answer",
    kickstartKpiHint:
      "The proposals will be saved into the primary KPI field as a semicolon-separated list.",
    kickstartProblemStatement: "Problem statement",
    kickstartAiSolution: "AI solution",
    kickstartKpiProposals: "KPI proposals",
    kickstartValueHypotheses: "Value hypotheses",
    kickstartRisks: "Risks",
    kickstartMissingInfoTitle: "Missing information",
    recommendationSummary: "Recommendation summary",
    submittedVersion: "Submitted version",
    questionRequired: "required",
    saveDraft: "Save draft",
    requestInformation: "Request information",
    requestInformationUnavailable:
      "This action stays unavailable until an authorized API can persist an information request.",
    stepCurrent: "Current",
    stepComplete: "Complete",
    stepPending: "Pending",
    chooseOption: "Choose…",
    aiAssisted: "AI-assisted",
    currencySuffix: "EUR",
    validationSummaryTitle: "Fix the following fields before continuing",
    validationSummaryDescription:
      "Each link moves focus back to the related field.",
  },
};
