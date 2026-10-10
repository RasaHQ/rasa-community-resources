import React from 'react';
import { SiteScore, ComparisonResult } from '../types';
import VoiceAssistantOrb from './assistant/VoiceAssistantOrb';

export default function FloatingAssistant({ siteResult, comparisonResult }: {
  siteResult?: SiteScore | null; comparisonResult?: ComparisonResult | null;
}) {
  return (
    <VoiceAssistantOrb
      siteResult={siteResult}
      comparisonResult={comparisonResult}
    />
  );
}