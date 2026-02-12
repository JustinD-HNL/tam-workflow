import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppLayout } from './layouts/AppLayout';
import {
  Dashboard,
  Customers,
  CustomerForm,
  TranscriptUpload,
  ApprovalQueue,
  Documents,
  LinearIssues,
  SlackMentions,
  HealthDashboard,
  Settings,
} from './pages';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/customers" element={<Customers />} />
          <Route path="/customers/new" element={<CustomerForm />} />
          <Route path="/customers/:id" element={<CustomerForm />} />
          <Route path="/transcripts" element={<TranscriptUpload />} />
          <Route path="/approvals" element={<ApprovalQueue />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/issues" element={<LinearIssues />} />
          <Route path="/mentions" element={<SlackMentions />} />
          <Route path="/health" element={<HealthDashboard />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
