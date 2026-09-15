import React from 'react';
import Landing from './components/landing/Landing';
import FloatingAssistant from './components/FloatingAssistant';
import LanguageChooser from './i18n/LanguageChooser';
import { useI18n } from './i18n/LanguageContext';

function AppContent() {
  return (
    <>
      <Landing />
      <FloatingAssistant />
    </>
  );
}

export default function App() {
  const { isChosen } = useI18n();

  if (!isChosen) {
    return <LanguageChooser />;
  }

  return <AppContent />;
}