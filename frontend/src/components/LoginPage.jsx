// frontend/src/components/LoginPage.jsx
import React, { useState } from 'react';

const LoginPage = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const response = await fetch("http://localhost:8000/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });

      const data = await response.json();

      if (data.success) {
        localStorage.setItem("session_id", data.session_id);
        localStorage.setItem("client_name", data.client.prenom + " " + data.client.nom);
        localStorage.setItem("client_id", data.client.id);
        
        console.log("✅ Connexion réussie:", data.client);
        
        if (onLoginSuccess) {
          onLoginSuccess();
        }
      } else {
        setError(data.error || "Email ou mot de passe incorrect");
      }
    } catch (err) {
      console.error("Erreur de connexion:", err);
      setError("Service indisponible. Veuillez réessayer plus tard.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: '#FFFFFF',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: "'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
      padding: '24px',
    }}>

      {/* Logo en haut */}
      <div style={{ marginBottom: 42, display: 'flex', justifyContent: 'center' }}>
        <img
          src="/Capture d'écran 2026-05-03 203553.png"
          alt="Attijariwafa Bank"
          style={{
            height: 100,
            width: 'auto',
            objectFit: 'contain',
          }}
        />
      </div>

      {/* Carte de connexion */}
      <div style={{
        width: '92%',
        maxWidth: 400,
        background: '#FFFFFF',
        textAlign: 'center',
        border: '1px solid #E5E7EB',
        borderRadius: 24,
        padding: '32px',
        boxShadow: '0 4px 20px rgba(0,0,0,0.05)',
      }}>

        {/* Avatar */}
        <div style={{
          width: 80,
          height: 80,
          borderRadius: '50%',
          background: '#F26522',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 28,
          fontWeight: 600,
          color: '#FFFFFF',
          margin: '0 auto 16px auto',
        }}>
          
        </div>

        <h2 style={{
          fontSize: 22,
          fontWeight: 600,
          color: '#1A1A1A',
          margin: '0 0 8px 0',
        }}>
          Accès client
        </h2>
        <p style={{
          fontSize: 13,
          color: '#6C757D',
          margin: '0 0 32px 0',
        }}>
          Connectez-vous avec votre email et mot de passe
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{
              width: '100%',
              padding: '14px 16px',
              fontSize: 15,
              border: '1px solid #E0E0E0',
              borderRadius: 12,
              outline: 'none',
              background: '#F9FAFB',
              fontFamily: 'inherit',
              boxSizing: 'border-box',
            }}
            onFocus={(e) => e.target.style.borderColor = '#F26522'}
            onBlur={(e) => e.target.style.borderColor = '#E0E0E0'}
            required
          />
          <input
            type="password"
            placeholder="Mot de passe"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{
              width: '100%',
              padding: '14px 16px',
              fontSize: 15,
              border: '1px solid #E0E0E0',
              borderRadius: 12,
              outline: 'none',
              background: '#F9FAFB',
              fontFamily: 'inherit',
              boxSizing: 'border-box',
            }}
            onFocus={(e) => e.target.style.borderColor = '#F26522'}
            onBlur={(e) => e.target.style.borderColor = '#E0E0E0'}
            required
          />
          {error && <p style={{ color: '#dc2626', fontSize: 12, margin: 0 }}>{error}</p>}
          <button
            type="submit"
            disabled={isLoading}
            style={{
              width: '100%',
              padding: '14px',
              fontSize: 16,
              fontWeight: 600,
              border: 'none',
              borderRadius: 40,
              background: isLoading ? '#CCCCCC' : '#F26522',
              color: '#FFFFFF',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit',
              marginTop: 8,
            }}
          >
            {isLoading ? 'Connexion...' : 'Se connecter'}
          </button>
        </form>

        <div style={{ marginTop: 24 }}>
          <a
            href="#"
            style={{
              color: '#F26522',
              fontSize: 12,
              fontWeight: 500,
              textDecoration: 'none',
            }}
          >
            Mot de passe oublié ?
          </a>
        </div>

        <div style={{ marginTop: 32, paddingTop: 16, borderTop: '1px solid #E5E7EB' }}>
          <button
            style={{
              padding: '12px 24px',
              fontSize: 14,
              fontWeight: 600,
              border: '2px solid #F26522',
              borderRadius: 40,
              background: 'transparent',
              color: '#F26522',
              cursor: 'pointer',
              fontFamily: 'inherit',
              width: '100%',
            }}
          >
            Devenir client
          </button>
        </div>
      </div>

      {/* Comptes de démonstration */}
      <div style={{ marginTop: 32, textAlign: 'center', fontSize: 12, color: '#9CA3AF' }}>
        <p style={{ fontWeight: 600, marginBottom: 8 }}>Comptes de démonstration :</p>
        <p> nabila.imouzaz@awb.ma /  nabila20</p>
        <p>farid@awb.ma /  farid20</p>
        <p> ahmed@awb.ma /  ahmed123</p>
        <p> fatima@awb.ma /  fatima456</p>
        <p>sofia@awb.ma /  sofia123</p>
      </div>
    </div>
  );
};

export default LoginPage;