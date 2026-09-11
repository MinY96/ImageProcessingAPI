import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell';
import { RecipeStudioPage } from '../pages/RecipeStudioPage';
import { ImageLabPage } from '../pages/ImageLabPage';
import { DatasetPage } from '../pages/DatasetPage';
import { EvaluationPage } from '../pages/EvaluationPage';
import { SettingsPage } from '../pages/SettingsPage';

export function App() {
  return <Routes>
    <Route element={<AppShell />}>
      <Route index element={<Navigate to="/recipe-studio" replace />} />
      <Route path="recipe-studio" element={<RecipeStudioPage />} />
      <Route path="image-lab" element={<ImageLabPage />} />
      <Route path="datasets" element={<DatasetPage />} />
      <Route path="evaluations" element={<EvaluationPage />} />
      <Route path="settings" element={<SettingsPage />} />
    </Route>
  </Routes>;
}
