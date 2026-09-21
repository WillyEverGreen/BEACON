import React, { createContext, useContext, useEffect, useState } from "react";
import axios from "axios";

export const BEACON_CONFIG = {
  version: '2.7.0',
  name: 'BEACON Engine',
  tagline: 'Accessibility Intelligence for the Modern Web',
  scanModes: [
    { id: 'fast', name: 'Fast Scan', description: 'Surface-level checks in <15s', icon: 'Zap' },
    { id: 'balanced', name: 'Balanced', description: 'Deep audit with precision scoring', icon: 'Scale' },
    { id: 'max', name: 'Max Intelligence', description: 'Full AI-remediation and journey simulation', icon: 'Brain' }
  ],
  thresholds: {
    critical: 90,
    warning: 70,
  }
};

interface BeaconConfigContextType {
  aiEnabled: boolean;
  config: typeof BEACON_CONFIG;
}

const BeaconConfigContext = createContext<BeaconConfigContextType>({
  aiEnabled: true,
  config: BEACON_CONFIG,
});

export function BeaconConfigProvider({ children }: { children: React.ReactNode }) {
  const [aiEnabled, setAiEnabled] = useState<boolean>(true);

  useEffect(() => {
    let active = true;
    axios.get("/api/beacon/config")
      .then((res) => {
        if (active && res.data && typeof res.data.aiEnabled === "boolean") {
          setAiEnabled(res.data.aiEnabled);
        }
      })
      .catch((err) => {
        console.warn("Failed to fetch dynamic beacon config, falling back to local defaults:", err);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <BeaconConfigContext.Provider value={{ aiEnabled, config: BEACON_CONFIG }}>
      {children}
    </BeaconConfigContext.Provider>
  );
}

export function useBeaconConfig() {
  return useContext(BeaconConfigContext);
}
