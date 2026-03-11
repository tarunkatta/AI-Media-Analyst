import React, { useEffect, useState } from 'react';
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from './firebase';
import Login from './components/Login.jsx';
import Upload from './components/Upload.jsx';

function App() {
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      if (!isMounted) return;
      setUser(firebaseUser || null);
      setAuthLoading(false);
    });

    return () => {
      isMounted = false;
      unsubscribe();
    };
  }, []);

  if (authLoading) {
    return (
      <div className="app-root loading-screen">
        <div className="spinner" aria-label="Loading" />
        <p className="loading-text">Initialising secure session…</p>
      </div>
    );
  }

  if (!user) {
    return <Login />;
  }

  return <Upload user={user} />;
}

export default App;

