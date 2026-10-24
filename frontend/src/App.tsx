import { BrowserRouter, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import { AppProvider } from './lib/store';
import Analysis from './pages/Analysis';
import Batch from './pages/Batch';
import Compare from './pages/Compare';
import Dashboard from './pages/Dashboard';
import Enrolled from './pages/Enrolled';
import Help from './pages/Help';
import ImageAnalyzer from './pages/ImageAnalyzer';
import Live from './pages/Live';
import Liveness from './pages/Liveness';
import Models from './pages/Models';
import Privacy from './pages/Privacy';
import Recognition from './pages/Recognition';
import Reports from './pages/Reports';
import SettingsPage from './pages/Settings';
import Tracking from './pages/Tracking';
import VideoAnalyzer from './pages/VideoAnalyzer';

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/live" element={<Live />} />
            <Route path="/analysis" element={<Analysis />} />
            <Route path="/recognition" element={<Recognition />} />
            <Route path="/enrolled" element={<Enrolled />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="/image" element={<ImageAnalyzer />} />
            <Route path="/video" element={<VideoAnalyzer />} />
            <Route path="/batch" element={<Batch />} />
            <Route path="/tracking" element={<Tracking />} />
            <Route path="/liveness" element={<Liveness />} />
            <Route path="/privacy" element={<Privacy />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/models" element={<Models />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/help" element={<Help />} />
            <Route path="*" element={<Dashboard />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </AppProvider>
  );
}
