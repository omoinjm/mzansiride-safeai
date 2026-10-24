import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router'
import './index.css'
import Layout from './components/Layout'
import BookPage from './pages/BookPage'
import TripPage from './pages/TripPage'
import AssistantPage from './pages/AssistantPage'
import WhatsAppPage from './pages/WhatsAppPage'
import DashboardPage from './pages/DashboardPage'
import AboutPage from './pages/AboutPage'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<BookPage />} />
          <Route path="trip/:id" element={<TripPage />} />
          <Route path="assistant" element={<AssistantPage />} />
          <Route path="whatsapp" element={<WhatsAppPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="about" element={<AboutPage />} />
          <Route path="*" element={<BookPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
