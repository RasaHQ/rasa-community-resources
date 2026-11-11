import React from 'react';
import Navbar from './Navbar';
import HeroSection from './HeroSection';
import FeatureSection from './FeatureSection';
import AboutSection from './AboutSection';
import ContactSection from './ContactSection';
import Footer from './Footer';

export function Landing() {
  return (
    <div className="landing">
      <Navbar />
      <HeroSection />
      <FeatureSection />
      <AboutSection />
      <ContactSection />
      <Footer />
    </div>
  );
}

export default Landing;