import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-[var(--studio-background)] px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-5xl flex-col gap-8">
        <section className="rounded-[var(--radius-xl)] border border-[var(--studio-border)] bg-[var(--studio-surface)] p-6 shadow-[var(--shadow-md)] sm:p-8">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--studio-brand)]">
            TIFINIA AI Value Studio
          </p>
          <h1 className="mt-3 font-serif text-4xl leading-tight text-[var(--studio-foreground)]">
            L’assessment S4 se pilote désormais depuis le détail d’un cas d’usage.
          </h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-[var(--studio-muted)]">
            Le wizard huit étapes persisté, versionné et auditable est intégré au parcours
            espace → programme → cas d’usage, tout en conservant l’export statique du client.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/studio"
              className="inline-flex min-h-10 items-center justify-center rounded-[var(--radius-md)] bg-[var(--studio-brand)] px-4 py-2 text-sm font-semibold text-white shadow-[var(--shadow-sm)] hover:bg-[var(--studio-brand-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--studio-focus)]"
            >
              Ouvrir le studio
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
