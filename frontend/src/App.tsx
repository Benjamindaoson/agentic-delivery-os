import { BrowserRouter, Routes, Route } from 'react-router-dom'
import DeliveryWizard from './pages/DeliveryWizard'
import TaskStatus from './pages/TaskStatus'
import ExecutionOverview from './pages/ExecutionOverview'
import ExecutionPlanDAG from './pages/ExecutionPlanDAG'
import SystemTimeline from './pages/SystemTimeline'
import AgentReports from './pages/AgentReports'
import ToolExecutions from './pages/ToolExecutions'
import PausedResume from './pages/PausedResume'
import ExecutionReplay from './pages/ExecutionReplay'
import CostOutcome from './pages/CostOutcome'
import FailureExplain from './pages/FailureExplain'
import Home from './pages/Home'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/wizard" element={<DeliveryWizard />} />
        <Route path="/task/:taskId" element={<TaskStatus />} />
        <Route path="/task/:taskId/overview" element={<ExecutionOverview />} />
        <Route path="/task/:taskId/plan" element={<ExecutionPlanDAG />} />
        <Route path="/task/:taskId/timeline" element={<SystemTimeline />} />
        <Route path="/task/:taskId/agents" element={<AgentReports />} />
        <Route path="/task/:taskId/tools" element={<ToolExecutions />} />
        <Route path="/task/:taskId/paused" element={<PausedResume />} />
        <Route path="/task/:taskId/replay" element={<ExecutionReplay />} />
        <Route path="/task/:taskId/cost" element={<CostOutcome />} />
        <Route path="/task/:taskId/failure" element={<FailureExplain />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App

