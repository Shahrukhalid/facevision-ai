import { useState } from 'react';
import CameraView from '../components/CameraView';
import FacePanel from '../components/FacePanel';
import { PageHeader } from '../components/ui';
import type { FrameResult } from '../lib/types';

export default function Live() {
  const [result, setResult] = useState<FrameResult | null>(null);
  return (
    <div>
      <PageHeader
        title="Live Face Detection"
        subtitle="Detects every face in the camera view, assigns temporary tracking IDs and draws the results. Choose a performance mode to trade detail for frame rate."
      />
      <CameraView
        pageName="Live Face Detection"
        onResult={setResult}
        controls={['preset', 'detection', 'tracking', 'landmarks', 'expression', 'recognition', 'age', 'attributes', 'appearance', 'pose', 'blur', 'threshold', 'source']}
      />
      {result && result.faces.length > 0 && (
        <div className="mt-4 grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {result.faces.slice(0, 6).map((f) => <FacePanel key={f.track_id ?? f.index} face={f} />)}
        </div>
      )}
    </div>
  );
}
