"use client";

import Link from "next/link";

export default function ImpressumPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-blue-900 text-white">
      <div className="max-w-3xl mx-auto px-8 py-16">
        {/* Navigation */}
        <nav className="flex items-center justify-between mb-12">
          <Link href="/" className="text-2xl font-bold">
            Signal<span className="text-blue-400">DACH</span>
          </Link>
          <Link
            href="/dashboard"
            className="px-5 py-2 bg-blue-600 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            Dashboard
          </Link>
        </nav>

        <h1 className="text-3xl font-bold mb-8">Impressum</h1>

        <div className="space-y-8 text-slate-300 leading-relaxed">
          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              Angaben gemäß § 5 TMG
            </h2>
            <p>
              [Firmenname GmbH]
              <br />
              [Straße und Hausnummer]
              <br />
              [PLZ Ort]
              <br />
              Deutschland
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              Vertreten durch
            </h2>
            <p>[Geschäftsführer: Vor- und Nachname]</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">Kontakt</h2>
            <p>
              E-Mail: info@signaldach.com
              <br />
              Telefon: [Telefonnummer]
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              Handelsregister
            </h2>
            <p>
              Registergericht: [Amtsgericht Ort]
              <br />
              Registernummer: [HRB XXXXX]
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              Umsatzsteuer-Identifikationsnummer
            </h2>
            <p>
              Umsatzsteuer-Identifikationsnummer gemäß § 27 a
              Umsatzsteuergesetz:
              <br />
              [DE XXXXXXXXX]
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              Verantwortlich für den Inhalt nach § 55 Abs. 2 RStV
            </h2>
            <p>
              [Vor- und Nachname]
              <br />
              [Straße und Hausnummer]
              <br />
              [PLZ Ort]
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              Streitschlichtung
            </h2>
            <p>
              Die Europäische Kommission stellt eine Plattform zur
              Online-Streitbeilegung (OS) bereit:{" "}
              <a
                href="https://ec.europa.eu/consumers/odr/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300 underline"
              >
                https://ec.europa.eu/consumers/odr/
              </a>
            </p>
            <p className="mt-2">
              Wir sind nicht bereit oder verpflichtet, an
              Streitbeilegungsverfahren vor einer Verbraucherschlichtungsstelle
              teilzunehmen.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              Haftung für Inhalte
            </h2>
            <p>
              Als Diensteanbieter sind wir gemäß § 7 Abs.1 TMG für eigene
              Inhalte auf diesen Seiten nach den allgemeinen Gesetzen
              verantwortlich. Nach §§ 8 bis 10 TMG sind wir als
              Diensteanbieter jedoch nicht verpflichtet, übermittelte oder
              gespeicherte fremde Informationen zu überwachen oder nach
              Umständen zu forschen, die auf eine rechtswidrige Tätigkeit
              hinweisen.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              Haftung für Links
            </h2>
            <p>
              Unser Angebot enthält Links zu externen Websites Dritter, auf
              deren Inhalte wir keinen Einfluss haben. Deshalb können wir für
              diese fremden Inhalte auch keine Gewähr übernehmen. Für die
              Inhalte der verlinkten Seiten ist stets der jeweilige Anbieter
              oder Betreiber der Seiten verantwortlich.
            </p>
          </section>
        </div>

        {/* Footer Links */}
        <div className="mt-16 pt-8 border-t border-white/10 flex gap-6 text-sm text-slate-500">
          <Link href="/impressum" className="hover:text-white transition-colors">
            Impressum
          </Link>
          <Link href="/datenschutz" className="hover:text-white transition-colors">
            Datenschutz
          </Link>
          <Link href="/agb" className="hover:text-white transition-colors">
            AGB
          </Link>
        </div>
      </div>
    </div>
  );
}
