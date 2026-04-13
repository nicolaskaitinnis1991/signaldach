"use client";

import Link from "next/link";

export default function DatenschutzPage() {
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

        <h1 className="text-3xl font-bold mb-8">Datenschutzerklärung</h1>

        <div className="space-y-8 text-slate-300 leading-relaxed">
          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              1. Verantwortliche Stelle
            </h2>
            <p>
              Verantwortlich für die Datenverarbeitung auf dieser Website ist:
            </p>
            <p className="mt-2">
              [Firmenname GmbH]
              <br />
              [Straße und Hausnummer]
              <br />
              [PLZ Ort]
              <br />
              E-Mail: info@signaldach.com
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              2. Erhebung und Speicherung personenbezogener Daten
            </h2>
            <p>
              Beim Besuch unserer Website werden automatisch Informationen
              allgemeiner Natur erfasst. Diese Informationen (Server-Logfiles)
              beinhalten etwa die Art des Webbrowsers, das verwendete
              Betriebssystem, den Domainnamen Ihres Internet-Service-Providers,
              Ihre IP-Adresse und Ähnliches.
            </p>
            <p className="mt-2">Dies geschieht insbesondere zu folgenden Zwecken:</p>
            <ul className="list-disc list-inside mt-2 space-y-1">
              <li>
                Sicherstellung eines problemlosen Verbindungsaufbaus der Website
              </li>
              <li>Sicherstellung einer reibungslosen Nutzung unserer Website</li>
              <li>Auswertung der Systemsicherheit und -stabilität</li>
              <li>Zu weiteren administrativen Zwecken</li>
            </ul>
            <p className="mt-2">
              Ihre Daten werden nicht verwendet, um Rückschlüsse auf Ihre Person
              zu ziehen. Die Rechtsgrundlage für die Datenverarbeitung ist Art. 6
              Abs. 1 S. 1 lit. f DSGVO.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              3. Cookies und Tracking
            </h2>
            <p>
              Unsere Website verwendet derzeit <strong>keine Cookies</strong> und{" "}
              <strong>keine Tracking-Technologien</strong>. Wir setzen keine
              Analyse-Tools wie Google Analytics, Matomo oder ähnliche Dienste
              ein.
            </p>
            <p className="mt-2">
              Sollte sich dies in Zukunft ändern, werden wir diese
              Datenschutzerklärung entsprechend aktualisieren und Sie vor der
              Verwendung von Cookies um Ihre Einwilligung bitten.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              4. Datenverarbeitung auf dieser Website
            </h2>
            <p>
              SignalDACH ist eine Marktintelligenz-Plattform, die öffentlich
              verfügbare Informationen aus RSS-Feeds, Nachrichtenquellen und
              regulatorischen Veröffentlichungen aggregiert und analysiert.
            </p>
            <p className="mt-2">
              Die von uns verarbeiteten Daten umfassen:
            </p>
            <ul className="list-disc list-inside mt-2 space-y-1">
              <li>
                Öffentlich zugängliche Nachrichtenartikel und regulatorische
                Veröffentlichungen
              </li>
              <li>
                Von Ihnen eingegebene Konfigurationsdaten (z.B. Alert-Einstellungen)
              </li>
              <li>Technische Zugriffsdaten (Server-Logfiles)</li>
            </ul>
            <p className="mt-2">
              Die Verarbeitung erfolgt auf Grundlage von Art. 6 Abs. 1 lit. f
              DSGVO (berechtigtes Interesse an der Bereitstellung unseres
              Dienstes).
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              5. Rechte der betroffenen Personen
            </h2>
            <p>Sie haben folgende Rechte:</p>
            <ul className="list-disc list-inside mt-2 space-y-2">
              <li>
                <strong>Auskunftsrecht (Art. 15 DSGVO):</strong> Sie haben das
                Recht, Auskunft über Ihre von uns verarbeiteten
                personenbezogenen Daten zu verlangen.
              </li>
              <li>
                <strong>Recht auf Berichtigung (Art. 16 DSGVO):</strong> Sie
                haben das Recht, die Berichtigung unrichtiger oder die
                Vervollständigung Ihrer bei uns gespeicherten personenbezogenen
                Daten zu verlangen.
              </li>
              <li>
                <strong>Recht auf Löschung (Art. 17 DSGVO):</strong> Sie haben
                das Recht, die Löschung Ihrer bei uns gespeicherten
                personenbezogenen Daten zu verlangen, soweit nicht die
                Verarbeitung zur Ausübung des Rechts auf freie
                Meinungsäußerung, zur Erfüllung einer rechtlichen Verpflichtung
                oder aus Gründen des öffentlichen Interesses erforderlich ist.
              </li>
              <li>
                <strong>
                  Recht auf Einschränkung der Verarbeitung (Art. 18 DSGVO):
                </strong>{" "}
                Sie haben das Recht, die Einschränkung der Verarbeitung Ihrer
                personenbezogenen Daten zu verlangen.
              </li>
              <li>
                <strong>
                  Recht auf Datenübertragbarkeit (Art. 20 DSGVO):
                </strong>{" "}
                Sie haben das Recht, Ihre personenbezogenen Daten in einem
                strukturierten, gängigen und maschinenlesbaren Format zu
                erhalten.
              </li>
              <li>
                <strong>Widerspruchsrecht (Art. 21 DSGVO):</strong> Sie haben
                das Recht, aus Gründen, die sich aus Ihrer besonderen Situation
                ergeben, jederzeit gegen die Verarbeitung Ihrer
                personenbezogenen Daten Widerspruch einzulegen.
              </li>
              <li>
                <strong>
                  Recht auf Widerruf der Einwilligung (Art. 7 Abs. 3 DSGVO):
                </strong>{" "}
                Sie haben das Recht, Ihre einmal erteilte Einwilligung jederzeit
                gegenüber uns zu widerrufen.
              </li>
              <li>
                <strong>
                  Beschwerderecht bei einer Aufsichtsbehörde (Art. 77 DSGVO):
                </strong>{" "}
                Sie haben das Recht, sich bei einer Aufsichtsbehörde zu
                beschweren, wenn Sie der Ansicht sind, dass die Verarbeitung
                Ihrer personenbezogenen Daten gegen die DSGVO verstößt.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              6. SSL-/TLS-Verschlüsselung
            </h2>
            <p>
              Diese Seite nutzt aus Sicherheitsgründen und zum Schutz der
              Übertragung vertraulicher Inhalte eine SSL-/TLS-Verschlüsselung.
              Eine verschlüsselte Verbindung erkennen Sie daran, dass die
              Adresszeile des Browsers von &quot;http://&quot; auf
              &quot;https://&quot; wechselt und an dem Schloss-Symbol in Ihrer
              Browserzeile.
            </p>
            <p className="mt-2">
              Wenn die SSL-/TLS-Verschlüsselung aktiviert ist, können die
              Daten, die Sie an uns übermitteln, nicht von Dritten mitgelesen
              werden.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-white mb-3">
              7. Änderung dieser Datenschutzerklärung
            </h2>
            <p>
              Wir behalten uns vor, diese Datenschutzerklärung anzupassen, damit
              sie stets den aktuellen rechtlichen Anforderungen entspricht oder
              um Änderungen unserer Leistungen in der Datenschutzerklärung
              umzusetzen. Für Ihren erneuten Besuch gilt dann die neue
              Datenschutzerklärung.
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
