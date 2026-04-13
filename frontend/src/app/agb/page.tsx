"use client";

import Link from "next/link";

export default function AGBPage() {
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

        <h1 className="text-3xl font-bold mb-8">
          Allgemeine Geschäftsbedingungen (AGB)
        </h1>

        <div className="space-y-8 text-slate-300 leading-relaxed">
          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              § 1 Geltungsbereich
            </h2>
            <p>
              Diese Allgemeinen Geschäftsbedingungen gelten für die Nutzung der
              Plattform SignalDACH (nachfolgend &quot;Dienst&quot;), betrieben
              von [Firmenname GmbH], [Adresse] (nachfolgend
              &quot;Anbieter&quot;).
            </p>
            <p className="mt-2">
              Mit der Registrierung oder Nutzung des Dienstes erkennt der Nutzer
              diese AGB an. Abweichende Bedingungen des Nutzers werden nicht
              anerkannt, es sei denn, der Anbieter stimmt ihrer Geltung
              ausdrücklich schriftlich zu.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              § 2 Leistungsbeschreibung
            </h2>
            <p>
              SignalDACH ist eine Marktintelligenz-Plattform für den
              Kryptomarkt in der DACH-Region. Der Dienst umfasst:
            </p>
            <ul className="list-disc list-inside mt-2 space-y-1">
              <li>
                Aggregation und Analyse öffentlich zugänglicher Nachrichten und
                regulatorischer Veröffentlichungen
              </li>
              <li>
                KI-gestützte Sentimentanalyse und Relevanzbewertunung
              </li>
              <li>
                Konfigurierbare Benachrichtigungen und Alerts
              </li>
              <li>
                Dashboard mit Analysefunktionen und Trendübersichten
              </li>
            </ul>
            <p className="mt-2">
              Der Anbieter behält sich das Recht vor, den Funktionsumfang des
              Dienstes jederzeit zu ändern, zu erweitern oder einzuschränken.
              Ein Anspruch auf Aufrechterhaltung bestimmter Funktionen besteht
              nicht.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              § 3 Nutzungsbedingungen
            </h2>
            <p>
              Der Nutzer verpflichtet sich, den Dienst nur im Rahmen der
              geltenden Gesetze zu nutzen. Insbesondere ist es untersagt:
            </p>
            <ul className="list-disc list-inside mt-2 space-y-1">
              <li>
                Den Dienst für illegale Zwecke oder zur Marktmanipulation zu
                verwenden
              </li>
              <li>
                Automatisierte Zugriffe (Scraping, Bots) ohne ausdrückliche
                Genehmigung durchzuführen
              </li>
              <li>
                Inhalte des Dienstes ohne Genehmigung zu vervielfältigen oder
                weiterzuverbreiten
              </li>
              <li>
                Sicherheitsmechanismen des Dienstes zu umgehen oder zu stören
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              § 4 Haftungsbeschränkung
            </h2>
            <p>
              Die über SignalDACH bereitgestellten Informationen dienen
              ausschließlich zu Informationszwecken und stellen keine
              Anlageberatung, Finanzberatung oder Empfehlung zum Kauf oder
              Verkauf von Kryptowährungen oder anderen Finanzinstrumenten dar.
            </p>
            <p className="mt-2">
              Der Anbieter übernimmt keine Gewähr für die Richtigkeit,
              Vollständigkeit oder Aktualität der bereitgestellten
              Informationen. Die Nutzung der Informationen erfolgt auf eigenes
              Risiko des Nutzers.
            </p>
            <p className="mt-2">
              Der Anbieter haftet nur für Schäden, die auf vorsätzlichem oder
              grob fahrlässigem Verhalten des Anbieters, seiner gesetzlichen
              Vertreter oder Erfüllungsgehilfen beruhen. Die Haftung für
              leichte Fahrlässigkeit ist ausgeschlossen, soweit keine
              wesentlichen Vertragspflichten verletzt werden.
            </p>
            <p className="mt-2">
              Die Haftung für Datenverlust wird auf den typischen
              Wiederherstellungsaufwand beschränkt, der bei regelmäßiger und
              gefahrentsprechender Anfertigung von Sicherungskopien eingetreten
              wäre.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              § 5 Verfügbarkeit
            </h2>
            <p>
              Der Anbieter bemüht sich um eine möglichst unterbrechungsfreie
              Verfügbarkeit des Dienstes. Durch notwendige Wartungsarbeiten,
              Weiterentwicklungen oder Störungen können Einschränkungen und
              Unterbrechungen auftreten. Eine Verfügbarkeitsgarantie besteht
              nur im Rahmen individuell vereinbarter Service Level Agreements
              (SLA).
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              § 6 Datenschutz
            </h2>
            <p>
              Der Schutz Ihrer personenbezogenen Daten ist uns wichtig.
              Informationen zur Erhebung und Verarbeitung personenbezogener
              Daten finden Sie in unserer{" "}
              <Link
                href="/datenschutz"
                className="text-blue-400 hover:text-blue-300 underline"
              >
                Datenschutzerklärung
              </Link>
              .
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              § 7 Geistiges Eigentum
            </h2>
            <p>
              Alle Inhalte des Dienstes, einschließlich Texte, Grafiken, Logos,
              Software und Datenbankinhalte, sind urheberrechtlich geschützt.
              Die Vervielfältigung, Bearbeitung, Verbreitung und jede Art der
              Verwertung außerhalb der Grenzen des Urheberrechtes bedürfen der
              schriftlichen Zustimmung des Anbieters.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              § 8 Schlussbestimmungen
            </h2>
            <p>
              Es gilt das Recht der Bundesrepublik Deutschland unter Ausschluss
              des UN-Kaufrechts.
            </p>
            <p className="mt-2">
              Gerichtsstand für alle Streitigkeiten aus oder im Zusammenhang
              mit diesem Vertrag ist, soweit gesetzlich zulässig, [Ort],
              Deutschland.
            </p>
            <p className="mt-2">
              Sollten einzelne Bestimmungen dieser AGB unwirksam sein oder
              werden, so bleibt die Wirksamkeit der übrigen Bestimmungen
              unberührt. An die Stelle der unwirksamen Bestimmung tritt eine
              wirksame Bestimmung, die dem wirtschaftlichen Zweck der
              unwirksamen Bestimmung am nächsten kommt.
            </p>
          </section>

          <section>
            <p className="text-sm text-slate-500">
              Stand: März 2026
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
