import type { ProgramStatus, UseCaseStatus, WorkspaceRole } from "@/features/api/types";

export type StudioLocale = "fr" | "en";

type StudioCopy = {
  appName: string;
  heroEyebrow: string;
  heroTitle: string;
  heroDescription: string;
  sessionActive: string;
  sessionInactive: string;
  noIdentity: string;
  signOut: string;
  auth: {
    cardTitle: string;
  };
  steps: {
    home: string;
    workspace: string;
    program: string;
    useCase: string;
    portfolio: string;
    members: string;
  };
  navigation: {
    primary: string;
    openMenu: string;
    closeMenu: string;
    home: string;
    workspace: string;
    program: string;
    useCase: string;
    portfolio: string;
    members: string;
    backToWorkspace: string;
    backToProgram: string;
    viewMembers: string;
  };
  common: {
    open: string;
    name: string;
    description: string;
    language: string;
    confidentiality: string;
    role: string;
    status: string;
    sponsor: string;
    consultant: string;
    owner: string;
    department: string;
    recommendation: string;
    category: string;
    priorityScore: string;
    title: string;
    strategicObjective: string;
    confidence: string;
    none: string;
    choose: string;
    noSponsor: string;
    noConsultant: string;
    noOwner: string;
    close: string;
  };
  home: {
    workspaceTitle: string;
    workspaceDescription: string;
    createWorkspace: string;
    workspaceCaption: string;
    workspaceHeaders: [string, string, string, string];
    noWorkspaceTitle: string;
    noWorkspaceDescription: string;
    activeIdentityTitle: string;
    activeIdentityDescription: string;
    activeIdentityName: string;
    activeIdentityRole: string;
    activeIdentitySubject: string;
    activeIdentityWorkspaceCount: string;
  };
  workspace: {
    defaultDescription: string;
    viewMembers: string;
    metadataDescription: string;
    programCaption: string;
    programHeaders: [string, string, string, string];
    emptyProgramsTitle: string;
    emptyProgramsDescription: string;
    createProgramTitle: string;
    createProgramDescription: string;
    inaccessibleTitle: string;
    inaccessibleDescription: string;
    objectiveFallback: string;
  };
  members: {
    title: string;
    description: string;
    deniedTitle: string;
    deniedDescription: string;
    caption: string;
    headers: [string, string, string, string];
    emptyTitle: string;
    emptyDescription: string;
    membershipId: string;
  };
  program: {
    notFoundTitle: string;
    notFoundDescription: string;
    defaultDescription: string;
    visibleUseCasesTitle: string;
    visibleUseCasesDescription: string;
    useCaseCaption: string;
    useCaseHeaders: [string, string, string, string];
    emptyUseCasesTitle: string;
    emptyUseCasesDescription: string;
    createUseCaseTitle: string;
    createUseCaseDescription: string;
    assignContributorTitle: string;
    assignContributorDescription: string;
    assignedSponsor: string;
    statusTransition: string;
    contributorToAssign: string;
    statusPlaceholder: string;
    departmentFallback: string;
    objectiveFallback: string;
  };
  useCase: {
    notFoundTitle: string;
    notFoundDescription: string;
    defaultDescription: string;
    navigationTitle: string;
    navigationDescription: string;
    ownerLabel: string;
    statusTransition: string;
  };
  forms: {
    createWorkspaceTitle: string;
    createWorkspaceDescription: string;
    workspaceName: string;
    defaultLanguage: string;
    confidentiality: string;
    create: string;
    createProgram: string;
    createUseCase: string;
    programName: string;
    strategicObjective: string;
    consultant: string;
    useCaseTitle: string;
    owner: string;
  };
  loading: {
    ariaLabel: string;
    retry: string;
  };
  toasts: {
    loadErrorTitle: string;
    loadErrorDetail: string;
    workspaceCreated: string;
    programCreated: string;
    useCaseCreated: string;
    programUpdated: string;
    useCaseUpdated: string;
    assignmentSaved: string;
    sponsorUpdated: string;
    ownerUpdated: string;
    authLoadFailed: string;
  };
};

const studioCopy: Record<StudioLocale, StudioCopy> = {
  fr: {
    appName: "TIFINIA AI Value Studio",
    heroEyebrow: "Studio de gouvernance IA",
    heroTitle: "Piloter les espaces, programmes et cas d’usage",
    heroDescription:
      "Une expérience statique, premium et gouvernée pour cadrer les initiatives IA du mandat jusqu’à la décision.",
    sessionActive: "Session active",
    sessionInactive: "Session inactive",
    noIdentity: "Aucune identité",
    signOut: "Se déconnecter",
    auth: {
      cardTitle: "Accéder au studio",
    },
    steps: {
      home: "Connexion",
      workspace: "Espace",
      program: "Programme",
      useCase: "Cas d’usage",
      portfolio: "Portefeuille",
      members: "Membres",
    },
    navigation: {
      primary: "Navigation principale",
      openMenu: "Ouvrir la navigation",
      closeMenu: "Fermer la navigation",
      home: "Connexion et espaces",
      workspace: "Espace",
      program: "Programme",
      useCase: "Cas d’usage",
      portfolio: "Portefeuille",
      members: "Membres",
      backToWorkspace: "Retour à l’espace",
      backToProgram: "Retour au programme",
      viewMembers: "Voir les membres",
    },
    common: {
      open: "Ouvrir",
      name: "Nom",
      description: "Description",
      language: "Langue",
      confidentiality: "Confidentialité",
      role: "Rôle",
      status: "Statut",
      sponsor: "Sponsor",
      consultant: "Consultant",
      owner: "Propriétaire",
      department: "Département",
      recommendation: "Recommandation",
      category: "Catégorie",
      priorityScore: "Priority score",
      title: "Titre",
      strategicObjective: "Objectif stratégique",
      confidence: "Niveau de confiance",
      none: "—",
      choose: "Choisir…",
      noSponsor: "Aucun sponsor",
      noConsultant: "Aucun consultant",
      noOwner: "Aucun propriétaire",
      close: "Fermer",
    },
    home: {
      workspaceTitle: "Espaces autorisés",
      workspaceDescription:
        "Accédez à un espace existant ou créez un nouvel espace si votre rôle vous y autorise.",
      createWorkspace: "Créer un espace de travail",
      workspaceCaption: "Liste des espaces visibles",
      workspaceHeaders: ["Nom", "Rôle", "Langue", "Accès"],
      noWorkspaceTitle: "Aucun espace visible",
      noWorkspaceDescription:
        "Associez cette identité à un espace existant ou créez-en un pour démarrer.",
      activeIdentityTitle: "Identité active",
      activeIdentityDescription:
        "Le bandeau et l’en-tête reflètent toujours l’identité actuellement sélectionnée.",
      activeIdentityName: "Nom",
      activeIdentityRole: "Rôle courant",
      activeIdentitySubject: "Subject",
      activeIdentityWorkspaceCount: "Espaces",
    },
    workspace: {
      defaultDescription: "Métadonnées de l’espace et programmes visibles.",
      viewMembers: "Voir les membres",
      metadataDescription: "Métadonnées de l’espace et programmes visibles.",
      programCaption: "Programmes de l’espace",
      programHeaders: ["Programme", "Statut", "Sponsor", "Accès"],
      emptyProgramsTitle: "Aucun programme",
      emptyProgramsDescription:
        "Créez un premier programme pour structurer les cas d’usage et leurs décisions.",
      createProgramTitle: "Créer un programme",
      createProgramDescription:
        "Disponible pour les Consultants et les administrateurs d’espace.",
      inaccessibleTitle: "Espace inaccessible",
      inaccessibleDescription:
        "L’espace demandé n’est pas visible pour l’identité courante.",
      objectiveFallback: "Objectif stratégique à préciser",
    },
    members: {
      title: "Membres de l’espace",
      description: "Vue d’administration dédiée à la gouvernance des accès.",
      deniedTitle: "Accès refusé",
      deniedDescription:
        "La liste des membres est réservée aux administrateurs d’espace.",
      caption: "Membres de l’espace",
      headers: ["Nom", "Rôle", "Statut", "Identifiant d’adhésion"],
      emptyTitle: "Aucun membre",
      emptyDescription:
        "Ajoutez des membres depuis l’API sécurisée afin de gouverner les affectations.",
      membershipId: "Identifiant d’adhésion",
    },
    program: {
      notFoundTitle: "Programme introuvable",
      notFoundDescription:
        "Le programme demandé n’est pas visible pour l’identité courante.",
      defaultDescription: "Objectif stratégique à compléter.",
      visibleUseCasesTitle: "Cas d’usage visibles",
      visibleUseCasesDescription:
        "Les Sponsors voient uniquement leur programme assigné. Les Contributors voient uniquement leur cas d’usage assigné.",
      useCaseCaption: "Cas d’usage du programme",
      useCaseHeaders: ["Cas d’usage", "Statut", "Propriétaire", "Accès"],
      emptyUseCasesTitle: "Aucun cas d’usage visible",
      emptyUseCasesDescription:
        "Affectez un contributeur puis renseignez le propriétaire du cas d’usage.",
      createUseCaseTitle: "Créer un cas d’usage",
      createUseCaseDescription:
        "Création réservée au Consultant ou à l’administrateur d’espace.",
      assignContributorTitle: "Affecter un contributeur",
      assignContributorDescription:
        "L’affectation au programme et le propriétaire du cas d’usage gouvernent la visibilité Contributor.",
      assignedSponsor: "Sponsor assigné",
      statusTransition: "Transition de statut",
      contributorToAssign: "Contributeur à affecter",
      statusPlaceholder: "Choisir…",
      departmentFallback: "Département à préciser",
      objectiveFallback: "Objectif stratégique à compléter.",
    },
    useCase: {
      notFoundTitle: "Cas d’usage introuvable",
      notFoundDescription:
        "Le cas d’usage demandé n’est pas visible pour l’identité courante.",
      defaultDescription: "Aucune recommandation encore saisie.",
      navigationTitle: "Navigation",
      navigationDescription:
        "Des routes statiques fondées sur des paramètres de requête, compatibles avec l’export statique.",
      ownerLabel: "Propriétaire du cas d’usage",
      statusTransition: "Transition de statut",
    },
    forms: {
      createWorkspaceTitle: "Créer un espace de travail",
      createWorkspaceDescription:
        "Le backend conserve l’audit et l’autorisation côté serveur.",
      workspaceName: "Nom",
      defaultLanguage: "Langue par défaut",
      confidentiality: "Confidentialité",
      create: "Créer",
      createProgram: "Créer le programme",
      createUseCase: "Créer le cas d’usage",
      programName: "Nom du programme",
      strategicObjective: "Objectif stratégique",
      consultant: "Consultant",
      useCaseTitle: "Titre",
      owner: "Propriétaire",
    },
    loading: {
      ariaLabel: "Chargement du studio",
      retry: "Réessayer",
    },
    toasts: {
      loadErrorTitle: "Chargement impossible",
      loadErrorDetail: "Le chargement a échoué.",
      workspaceCreated: "Espace créé",
      programCreated: "Programme créé",
      useCaseCreated: "Cas d’usage créé",
      programUpdated: "Programme mis à jour",
      useCaseUpdated: "Statut mis à jour",
      assignmentSaved: "Affectation enregistrée",
      sponsorUpdated: "Sponsor mis à jour",
      ownerUpdated: "Propriétaire mis à jour",
      authLoadFailed: "Chargement impossible",
    },
  },
  en: {
    appName: "TIFINIA AI Value Studio",
    heroEyebrow: "AI governance studio",
    heroTitle: "Steer workspaces, programs, and use cases",
    heroDescription:
      "A polished static experience to govern AI initiatives from intake to decision.",
    sessionActive: "Session active",
    sessionInactive: "Session inactive",
    noIdentity: "No identity selected",
    signOut: "Sign out",
    auth: {
      cardTitle: "Access the studio",
    },
    steps: {
      home: "Sign-in",
      workspace: "Workspace",
      program: "Program",
      useCase: "Use case",
      portfolio: "Portfolio",
      members: "Members",
    },
    navigation: {
      primary: "Primary navigation",
      openMenu: "Open navigation",
      closeMenu: "Close navigation",
      home: "Sign-in and workspaces",
      workspace: "Workspace",
      program: "Program",
      useCase: "Use case",
      portfolio: "Portfolio",
      members: "Members",
      backToWorkspace: "Back to workspace",
      backToProgram: "Back to program",
      viewMembers: "View members",
    },
    common: {
      open: "Open",
      name: "Name",
      description: "Description",
      language: "Language",
      confidentiality: "Confidentiality",
      role: "Role",
      status: "Status",
      sponsor: "Sponsor",
      consultant: "Consultant",
      owner: "Owner",
      department: "Department",
      recommendation: "Recommendation",
      category: "Category",
      priorityScore: "Priority score",
      title: "Title",
      strategicObjective: "Strategic objective",
      confidence: "Confidence",
      none: "—",
      choose: "Choose…",
      noSponsor: "No sponsor",
      noConsultant: "No consultant",
      noOwner: "No owner",
      close: "Close",
    },
    home: {
      workspaceTitle: "Authorized workspaces",
      workspaceDescription:
        "Open an existing workspace or create one when your role allows it.",
      createWorkspace: "Create workspace",
      workspaceCaption: "Visible workspaces",
      workspaceHeaders: ["Name", "Role", "Language", "Access"],
      noWorkspaceTitle: "No visible workspace",
      noWorkspaceDescription:
        "Assign this identity to a workspace or create one to get started.",
      activeIdentityTitle: "Active identity",
      activeIdentityDescription:
        "The banner and header always reflect the selected identity.",
      activeIdentityName: "Name",
      activeIdentityRole: "Current role",
      activeIdentitySubject: "Subject",
      activeIdentityWorkspaceCount: "Workspaces",
    },
    workspace: {
      defaultDescription: "Workspace metadata and visible programs.",
      viewMembers: "View members",
      metadataDescription: "Workspace metadata and visible programs.",
      programCaption: "Workspace programs",
      programHeaders: ["Program", "Status", "Sponsor", "Access"],
      emptyProgramsTitle: "No program",
      emptyProgramsDescription:
        "Create a first program to structure use cases and decisions.",
      createProgramTitle: "Create a program",
      createProgramDescription:
        "Available to Consultants and workspace administrators.",
      inaccessibleTitle: "Workspace unavailable",
      inaccessibleDescription:
        "The requested workspace is not visible for the current identity.",
      objectiveFallback: "Strategic objective to be defined",
    },
    members: {
      title: "Workspace members",
      description: "Dedicated administration view for access governance.",
      deniedTitle: "Access denied",
      deniedDescription: "The member list is reserved for workspace administrators.",
      caption: "Workspace members",
      headers: ["Name", "Role", "Status", "Membership ID"],
      emptyTitle: "No member",
      emptyDescription:
        "Add members from the secured API to govern assignments.",
      membershipId: "Membership ID",
    },
    program: {
      notFoundTitle: "Program not found",
      notFoundDescription:
        "The requested program is not visible for the current identity.",
      defaultDescription: "Strategic objective to be completed.",
      visibleUseCasesTitle: "Visible use cases",
      visibleUseCasesDescription:
        "Sponsors only see their assigned program. Contributors only see their assigned use case.",
      useCaseCaption: "Program use cases",
      useCaseHeaders: ["Use case", "Status", "Owner", "Access"],
      emptyUseCasesTitle: "No visible use case",
      emptyUseCasesDescription:
        "Assign a contributor and then set the use case owner.",
      createUseCaseTitle: "Create a use case",
      createUseCaseDescription:
        "Creation is reserved to the Consultant or workspace administrator.",
      assignContributorTitle: "Assign a contributor",
      assignContributorDescription:
        "Program assignment and use case ownership govern contributor visibility.",
      assignedSponsor: "Assigned sponsor",
      statusTransition: "Status transition",
      contributorToAssign: "Contributor to assign",
      statusPlaceholder: "Choose…",
      departmentFallback: "Department to be defined",
      objectiveFallback: "Strategic objective to be completed.",
    },
    useCase: {
      notFoundTitle: "Use case not found",
      notFoundDescription:
        "The requested use case is not visible for the current identity.",
      defaultDescription: "No recommendation has been captured yet.",
      navigationTitle: "Navigation",
      navigationDescription:
        "Static routes powered by query parameters, compatible with static export.",
      ownerLabel: "Use case owner",
      statusTransition: "Status transition",
    },
    forms: {
      createWorkspaceTitle: "Create workspace",
      createWorkspaceDescription:
        "The backend preserves audit and authorization server-side.",
      workspaceName: "Name",
      defaultLanguage: "Default language",
      confidentiality: "Confidentiality",
      create: "Create",
      createProgram: "Create program",
      createUseCase: "Create use case",
      programName: "Program name",
      strategicObjective: "Strategic objective",
      consultant: "Consultant",
      useCaseTitle: "Title",
      owner: "Owner",
    },
    loading: {
      ariaLabel: "Loading studio",
      retry: "Retry",
    },
    toasts: {
      loadErrorTitle: "Unable to load",
      loadErrorDetail: "Loading failed.",
      workspaceCreated: "Workspace created",
      programCreated: "Program created",
      useCaseCreated: "Use case created",
      programUpdated: "Program updated",
      useCaseUpdated: "Status updated",
      assignmentSaved: "Assignment saved",
      sponsorUpdated: "Sponsor updated",
      ownerUpdated: "Owner updated",
      authLoadFailed: "Unable to load",
    },
  },
};

const programStatusLabels: Record<StudioLocale, Record<ProgramStatus, string>> = {
  fr: {
    Draft: "Ébauche",
    Discovery: "Découverte",
    Assessment: "Évaluation",
    Prioritization: "Priorisation",
    Decision: "Décision",
    Closed: "Clôturé",
  },
  en: {
    Draft: "Draft",
    Discovery: "Discovery",
    Assessment: "Assessment",
    Prioritization: "Prioritization",
    Decision: "Decision",
    Closed: "Closed",
  },
};

const useCaseStatusLabels: Record<StudioLocale, Record<UseCaseStatus, string>> = {
  fr: {
    Draft: "Ébauche",
    InProgress: "En cours",
    Submitted: "Soumis",
    ChangesRequested: "Révisions demandées",
    Approved: "Approuvé",
    Rejected: "Rejeté",
  },
  en: {
    Draft: "Draft",
    InProgress: "In progress",
    Submitted: "Submitted",
    ChangesRequested: "Changes requested",
    Approved: "Approved",
    Rejected: "Rejected",
  },
};

const workspaceRoleLabels: Record<StudioLocale, Record<WorkspaceRole, string>> = {
  fr: {
    Consultant: "Consultant",
    Sponsor: "Sponsor",
    Contributor: "Contributeur",
    WorkspaceAdmin: "Admin espace",
  },
  en: {
    Consultant: "Consultant",
    Sponsor: "Sponsor",
    Contributor: "Contributor",
    WorkspaceAdmin: "Workspace admin",
  },
};

export function studioCopyFor(locale: StudioLocale): StudioCopy {
  return studioCopy[locale];
}

export function formatProgramStatusLabel(
  locale: StudioLocale,
  status: ProgramStatus,
): string {
  return programStatusLabels[locale][status];
}

export function formatUseCaseStatusLabel(
  locale: StudioLocale,
  status: UseCaseStatus,
): string {
  return useCaseStatusLabels[locale][status];
}

export function formatWorkspaceRoleLabel(
  locale: StudioLocale,
  role: WorkspaceRole,
): string {
  return workspaceRoleLabels[locale][role];
}
