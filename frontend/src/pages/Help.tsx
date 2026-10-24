import { ExternalLink } from 'lucide-react';
import { PageHeader } from '../components/ui';

const SECTIONS = [
  ['start', 'Getting started'],
  ['consent', 'Consent and privacy'],
  ['accuracy', 'Accuracy and limitations'],
  ['api', 'Using the API'],
  ['trouble', 'Troubleshooting'],
  ['licences', 'Models and licences'],
] as const;

export default function Help() {
  return (
    <div className="grid gap-8 lg:grid-cols-[200px_minmax(0,1fr)]">
      <nav className="top-20 h-max space-y-1 text-sm lg:sticky" aria-label="Help sections">
        {SECTIONS.map(([id, label]) => (
          <a key={id} href={`#${id}`} className="block rounded px-2 py-1 text-fog-400 hover:bg-ink-800 hover:text-fog-100">{label}</a>
        ))}
        <a href="/api/docs" target="_blank" rel="noreferrer" className="mt-3 flex items-center gap-1 rounded px-2 py-1 text-lens-300 hover:bg-ink-800">API reference <ExternalLink className="h-3 w-3" /></a>
      </nav>
      <article className="prose-doc min-w-0">
        <PageHeader title="Help & Documentation" subtitle="FaceVision AI runs entirely on this computer. These notes cover what it does, what it cannot do, and how to fix common problems." />

        <h2 id="start">Getting started</h2>
        <ul>
          <li>Open <strong>Model Manager</strong> and choose <em>Install defaults</em>. This downloads about 80 MB once and checks every file against its SHA-256 checksum.</li>
          <li>Open <strong>Live Face Detection</strong> and press <em>Start camera</em>. Your browser asks for camera permission the first time.</li>
          <li>To recognise people, set an access passphrase in <strong>Settings</strong>, then enrol consenting people in <strong>Enrolled Faces</strong> with 3–5 clear photos each.</li>
          <li>Performance modes: <em>Fast</em> detects and tracks only; <em>Balanced</em> adds landmarks, pose, blink and smile, quality, expression and recognition; <em>Detailed</em> adds age, attribute estimates and higher-resolution detection.</li>
        </ul>

        <h2 id="consent">Consent and privacy</h2>
        <ul>
          <li>Only enrol people who have agreed to it and understand how it is used. The enrolment form records when consent was confirmed.</li>
          <li>Recognition only compares faces with people enrolled on this computer. FaceVision AI never searches the internet or any external database.</li>
          <li>Enrolment photos are converted into face templates, encrypted with AES-256-GCM, and then discarded. The encryption key is only unlocked by your passphrase or API key.</li>
          <li>Live frames are processed in memory and never stored. Screenshots and recordings are saved only when you press the button, and a red indicator shows while the camera is on.</li>
          <li>Individual recognitions are not logged. The audit log records administrative actions such as enrolment and deletion.</li>
          <li>Deleting a person removes their templates from the database immediately. Backups you made earlier still contain them.</li>
          <li>Many places regulate biometric data (for example the GDPR in Europe and BIPA in Illinois). Check what applies to you before enrolling anyone.</li>
        </ul>

        <h2 id="accuracy">Accuracy and limitations</h2>
        <ul>
          <li><strong>Recognition</strong>: on the AT&amp;T face set (40 people, controlled lighting) the default SFace threshold of 0.363 gave no false rejections and a 0.17% false match rate in this project's tests. Real-world photos are harder: lighting, pose, age gaps, glasses and image quality all lower accuracy. A similarity score is not a probability that two photos show the same person.</li>
          <li><strong>Demographic differences</strong>: face recognition and attribute models can be less accurate for some groups. Use <code>python -m facevision evaluate</code> with a lawfully obtained, consented dataset and a groups file to measure this on your own data.</li>
          <li><strong>Age</strong> is shown as a range. It is an estimate of apparent age from appearance and can be far off.</li>
          <li><strong>Expressions</strong> describe what the face looks like (for example a smile). They are not evidence of emotions, intentions or mental state.</li>
          <li><strong>Appearance classifier</strong>: off by default. It predicts a binary label from appearance and cannot determine anyone's gender identity.</li>
          <li><strong>Attributes</strong> (glasses, mask, beard, mustache) and CLIP age brackets are experimental zero-shot estimates.</li>
          <li><strong>Liveness</strong>: webcam checks can be fooled by masks, good replays and real-time deepfakes. Use them as one signal, never as proof.</li>
          <li><strong>Tracking IDs</strong> are temporary numbers, not identities.</li>
        </ul>

        <h2 id="api">Using the API</h2>
        <p>The full, interactive reference is at <a className="text-lens-300 underline" href="/api/docs" target="_blank" rel="noreferrer">/api/docs</a>. Non-biometric endpoints need no key. Biometric endpoints (people, recognition, verification, data export) need a signed-in session or an API key from Settings.</p>
        <pre>{`# detect faces
curl -F file=@photo.jpg http://localhost:8600/api/detect

# full analysis with options
curl -F file=@photo.jpg -F 'options={"preset":"detailed"}' http://localhost:8600/api/analyze

# compare two photos
curl -F file_a=@a.jpg -F file_b=@b.jpg http://localhost:8600/api/compare

# blur every face
curl -F file=@photo.jpg -F method=blur -o blurred.jpg http://localhost:8600/api/anonymize

# recognise enrolled people (needs an API key)
curl -H "X-API-Key: fv_..." -F file=@photo.jpg http://localhost:8600/api/recognize`}</pre>
        <p>Live results stream over a WebSocket at <code>/ws/live</code>: send a JSON <code>{'{"type":"options","options":{...}}'}</code> message, then JPEG frames as binary messages; each frame gets one JSON result.</p>

        <h2 id="trouble">Troubleshooting</h2>
        <h3>The camera does not start</h3>
        <ul>
          <li>macOS: System Settings → Privacy &amp; Security → Camera, allow your browser, then reload the page.</li>
          <li>Windows: Settings → Privacy &amp; security → Camera, turn on camera access for desktop apps and your browser.</li>
          <li>Close other apps that use the camera (video calls, OBS).</li>
          <li>Open the app at <code>http://localhost:8600</code>. Browsers only allow cameras on secure pages, and localhost counts as secure.</li>
        </ul>
        <h3>A model fails to download</h3>
        <ul>
          <li>Check your internet connection or proxy. Downloads come from GitHub and Google's MediaPipe storage.</li>
          <li>On an offline computer, copy the files from another machine and run <code>python -m facevision models install --defaults --from-dir FOLDER</code>. Checksums are still verified.</li>
        </ul>
        <h3>It is slow</h3>
        <ul>
          <li>Switch to the Fast mode, turn off attributes and age, or lower the camera resolution.</li>
          <li>Run <code>python -m facevision bench</code> to measure each mode on your machine.</li>
        </ul>
        <h3>Port 8600 is in use</h3>
        <ul><li>Set <code>FV_PORT=8601</code> in the <code>.env</code> file and restart.</li></ul>
        <h3>I forgot my passphrase</h3>
        <ul><li>Use <em>Forgot passphrase</em> in Settings. Enrolled faces cannot be recovered without it and are deleted.</li></ul>

        <h2 id="licences">Models and licences</h2>
        <p>FaceVision AI's code is MIT-licensed. Models keep their own licences, which the Model Manager shows next to each one. The defaults (YuNet, SFace, MediaPipe Face Landmarker, FER+, Silent-Face anti-spoofing and CLIP) allow commercial use. The optional InsightFace pack is for non-commercial research only and is downloaded from InsightFace directly after you accept its terms.</p>
      </article>
    </div>
  );
}
