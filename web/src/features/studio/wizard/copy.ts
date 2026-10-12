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
  yes: string;
  no: string;
  currentStep: string;
  kickstartTitle: string;
  kickstartDescription: string;
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
    yes: "Oui",
    no: "Non",
    currentStep: "Étape en cours",
    kickstartTitle: "Kickstart IA",
    kickstartDescription:
      "Optionnel — l’assistance IA n’est pas disponible dans cette version. Aucune suggestion n’est simulée.",
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
    yes: "Yes",
    no: "No",
    currentStep: "Current step",
    kickstartTitle: "AI kickstart",
    kickstartDescription:
      "Optional — AI assistance is unavailable in this release. No suggestion is simulated.",
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
  },
};
