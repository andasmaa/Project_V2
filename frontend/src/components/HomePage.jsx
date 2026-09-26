// frontend/src/components/HomePage.jsx
import React from 'react';

const COLORS = {
  primary: "#F26522",
  secondary: "#FFC72C",
  dark: "#1A1A1A",
  light: "#FFFFFF",
  gray: "#6C757D",
  grayLight: "#F5F5F5",
  gold: "#C8922A",
};

const HomePage = ({ onGetStarted }) => {
  return (
    <div style={{ fontFamily: "'Segoe UI', 'Helvetica Neue', Arial, sans-serif", overflowX: 'hidden', margin: 0, padding: 0 }}>

      {/* ========== VIDÉO FIXE EN ARRIÈRE-PLAN ========== */}
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100vh',
        overflow: 'hidden',
        zIndex: 0,
      }}>
        <video
          autoPlay
          loop
          muted
          playsInline
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            minWidth: '100%',
            minHeight: '100%',
            width: 'auto',
            height: 'auto',
            transform: 'translate(-50%, -50%)',
            objectFit: 'cover',
          }}
        >
          <source src="/awb-bg-video.mov" type="video/mp4" />
          Votre navigateur ne supporte pas les vidéos.
        </video>

        {/* Overlay + léger pour que le texte soit lisible */}
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          background: 'linear-gradient(180deg, rgba(0,0,0,0.4) 0%, rgba(0,0,0,0.2) 40%, rgba(0,0,0,0.6) 100%)',
          zIndex: 1,
        }} />
      </div>

      {/* ========== CONTENU QUI SCROLLE (fond TRANSPARENT) ========== */}
      <div style={{
        position: 'relative',
        zIndex: 2,
        minHeight: '100vh',
      }}>

        {/* Navigation - fond légèrement transparent */}
        <nav style={{ background: '#FFFFFF', boxShadow: '0 1px 0 rgba(0,0,0,0.08)' }}>
          <div style={{ padding: '12px 48px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
              <img
                src="https://cdn.dribbble.com/users/6933358/screenshots/16122929/media/28b32a6a3b876f89520d1d6a38b4f432.gif"
                alt="Attijariwafa Bank Logo Animé"
                style={{ height: 150, width: 'auto', objectFit: 'contain', display: 'block' }}
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
                <a
                  href="#"
                  onClick={(e) => { e.preventDefault(); onGetStarted(); }}
                  style={{ background: COLORS.primary, color: '#FFF', padding: '8px 24px', borderRadius: 4, textDecoration: 'none', fontSize: 13, fontWeight: 600, letterSpacing: '0.3px' }}
                >
                  Services en ligne
                </a>
                <span style={{ color: '#ccc', fontSize: 16 }}>|</span>
                <a
                  href="#"
                  onClick={(e) => { e.preventDefault(); onGetStarted(); }}
                  style={{ textDecoration: 'none', color: COLORS.secondary, fontSize: 13, fontWeight: 600, background: COLORS.dark, padding: '7px 20px', borderRadius: 4 }}
                >
                  Banque en ligne
                </a>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 28, padding: '14px 0', overflowX: 'auto', borderTop: '1px solid #EBEBEB', marginTop: 12 }}>
              {["Accueil","Groupe","Infos financières","ESG","Fondation","Médiation bancaire","Carrières","Club Afrique Développement","Actualités","Médias"].map((item, i) => (
                <a key={item} href="#" style={{
                  textDecoration: 'none',
                  color: i === 0 ? COLORS.primary : '#333',
                  fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap',
                  paddingBottom: 4,
                  borderBottom: i === 0 ? `2px solid ${COLORS.primary}` : 'none',
                }}>
                  {item}
                </a>
              ))}
            </div>
          </div>
        </nav>

        {/* Hero Text - SUR LA VIDÉO (fond transparent) */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '100px 40px',
          textAlign: 'center',
          minHeight: '70vh',
        }}>
          <h1 style={{
            fontSize: 'clamp(48px, 7vw, 80px)',
            fontWeight: 700,
            color: '#FFFFFF',
            marginBottom: 50,
            textShadow: '0 2px 20px rgba(0,0,0,0.3)',
            letterSpacing: '-1px',
          }}>
            Croire en vous
          </h1>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', justifyContent: 'center' }}>
            {[" À chaque moment de la vie", "Qui que vous soyez", "Partout dans le monde", "Nos filiales à votre service"].map((text) => (
              <div key={text} style={{
                padding: '14px 28px',
                background: 'rgba(0,0,0,0.6)',
                backdropFilter: 'blur(10px)',
                borderRadius: 50,
                color: '#FFFFFF',
                fontSize: 15,
                fontWeight: 500,
                border: '1px solid rgba(255,255,255,0.2)',
              }}>
                {text}
              </div>
            ))}
          </div>
        </div>

        {/* Actualités - fond blanc pour contraste */}
        <div style={{ padding: '60px 60px', background: '#FFFFFF' }}>
          <div style={{ display: 'flex', gap: 40, justifyContent: 'center', flexWrap: 'wrap' }}>
            <div style={{
              width: 'clamp(320px, 45%, 580px)', background: '#FFF',
              borderRadius: 4, overflow: 'hidden',
              boxShadow: '0 2px 16px rgba(0,0,0,0.08)',
              borderBottom: `3px solid ${COLORS.primary}`,
            }}>
              <div style={{ width: '100%', height: 400, overflow: 'hidden' }}>
                <img src="/OIP (1).webp" alt="Sensibilisation" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
              </div>
              <div style={{ padding: '24px 28px' }}>
                <span style={{ display: 'block', fontSize: 11, fontWeight: 700, color: COLORS.primary, letterSpacing: '0.8px', textTransform: 'uppercase', marginBottom: 12 }}>ACTUALITÉ</span>
                <h3 style={{ fontSize: 18, fontWeight: 700, color: COLORS.dark, marginBottom: 10, lineHeight: 1.4 }}>Message de sensibilisation</h3>
                <p style={{ fontSize: 14, color: COLORS.gray, lineHeight: 1.6, margin: 0 }}>Sensibilisation à la sécurité bancaire et à la prévention des fraudes.</p>
              </div>
            </div>

            <div style={{
              width: 'clamp(320px, 45%, 580px)', background: '#FFF',
              borderRadius: 4, overflow: 'hidden',
              boxShadow: '0 2px 16px rgba(0,0,0,0.08)',
              borderBottom: `3px solid ${COLORS.primary}`,
            }}>
              <div style={{ width: '100%', height: 400, overflow: 'hidden' }}>
                <img src="/IMG_9665.jpeg" alt="Best Bank Morocco 2026" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
              </div>
              <div style={{ padding: '24px 28px' }}>
                <span style={{ display: 'block', fontSize: 11, fontWeight: 700, color: COLORS.primary, letterSpacing: '0.8px', textTransform: 'uppercase', marginBottom: 12 }}>ACTUALITÉ</span>
                <h3 style={{ fontSize: 18, fontWeight: 700, color: COLORS.dark, marginBottom: 10, lineHeight: 1.4 }}>BEST BANK IN MOROCCO 2026</h3>
                <p style={{ fontSize: 14, color: COLORS.gray, lineHeight: 1.6, margin: 0 }}>Attijariwafa bank distinguée par Global Finance — Best Bank in Morocco 2026.</p>
              </div>
            </div>
          </div>
        </div>

        {/* Liens */}
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'flex-start', padding: '40px 60px', background: '#FFF', borderTop: '1px solid #EBEBEB', borderBottom: '1px solid #EBEBEB', flexWrap: 'wrap' }}>
          <div style={{ padding: '0 60px', minWidth: 200 }}>
            <p style={{ fontSize: 15, fontWeight: 700, color: COLORS.dark, margin: '0 0 14px 0' }}>Nous rejoindre</p>
            <a href="#" style={{ display: 'block', color: COLORS.gold, fontSize: 14, fontWeight: 600, textDecoration: 'none', borderBottom: `1px solid ${COLORS.gold}`, paddingBottom: 2, width: 'fit-content' }}>Découvrir nos offres d'emploi</a>
          </div>
          <div style={{ width: 1, background: '#EBEBEB', alignSelf: 'stretch', margin: '0', minHeight: 60 }}></div>
          <div style={{ padding: '0 60px', minWidth: 200 }}>
            <p style={{ fontSize: 15, fontWeight: 700, color: COLORS.dark, margin: '0 0 14px 0' }}>Échanger avec nous</p>
            <a href="#" style={{ display: 'block', color: COLORS.gold, fontSize: 14, fontWeight: 600, textDecoration: 'none', borderBottom: `1px solid ${COLORS.gold}`, paddingBottom: 2, marginBottom: 8, width: 'fit-content' }}>Nous contacter</a>
            <a href="#" style={{ display: 'block', color: COLORS.gold, fontSize: 14, fontWeight: 600, textDecoration: 'none', borderBottom: `1px solid ${COLORS.gold}`, paddingBottom: 2, width: 'fit-content' }}>Réclamations</a>
          </div>
        </div>

        {/* Footer */}
        <footer style={{ background: '#2D2D2D' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', padding: '40px 60px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', paddingRight: 40, minWidth: 220 }}>
              <img
                src="/Capture d'écran 2026-05-03 180748.png"
                alt="Attijariwafa Bank Footer Logo"
                style={{ height: 100, width: 'auto', objectFit: 'contain' }}
              />
            </div>

            <div style={{ width: 1, background: 'rgba(255,255,255,0.12)', alignSelf: 'stretch', minHeight: 80, margin: '0 40px' }}></div>

            <div style={{ minWidth: 150, paddingRight: 12 }}>
              <p style={{ color: '#FFF', fontSize: 14, fontWeight: 600, margin: '0 0 14px 0' }}>Nous rejoindre</p>
              <a href="#" style={{ display: 'block', color: COLORS.gold, fontSize: 13, fontWeight: 600, textDecoration: 'none', marginBottom: 10, borderBottom: `1px solid ${COLORS.gold}`, paddingBottom: 2, width: 'fit-content' }}>Découvrir nos offres d'emploi</a>
            </div>

            <div style={{ width: 1, background: 'rgba(255,255,255,0.12)', alignSelf: 'stretch', minHeight: 80, margin: '0 40px' }}></div>

            <div style={{ minWidth: 150, paddingRight: 12 }}>
              <p style={{ color: '#FFF', fontSize: 14, fontWeight: 600, margin: '0 0 14px 0' }}>Echanger avec nous</p>
              <a href="#" style={{ display: 'block', color: COLORS.gold, fontSize: 13, fontWeight: 600, textDecoration: 'none', marginBottom: 10, borderBottom: `1px solid ${COLORS.gold}`, paddingBottom: 2, width: 'fit-content' }}>Nous contacter</a>
              <a href="#" style={{ display: 'block', color: COLORS.gold, fontSize: 13, fontWeight: 600, textDecoration: 'none', borderBottom: `1px solid ${COLORS.gold}`, paddingBottom: 2, width: 'fit-content' }}>Réclamations</a>
            </div>

            <div style={{ width: 1, background: 'rgba(255,255,255,0.12)', alignSelf: 'stretch', minHeight: 80, margin: '0 40px' }}></div>

            <div style={{ minWidth: 120 }}>
              <p style={{ color: '#FFF', fontSize: 14, fontWeight: 600, margin: '0 0 14px 0' }}>Nous suivre</p>
              <div style={{ display: 'flex', gap: 10 }}>
                {[{ l: 'in' }, { l: '▶' }, { l: 'f' }].map(({ l }) => (
                  <a key={l} href="#" style={{ width: 36, height: 36, borderRadius: 4, background: 'rgba(255,255,255,0.12)', color: '#FFF', display: 'flex', alignItems: 'center', justifyContent: 'center', textDecoration: 'none', fontSize: 12, fontWeight: 700 }}>{l}</a>
                ))}
              </div>
            </div>
          </div>

          <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', padding: '22px 60px 16px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px 24px', marginBottom: 10 }}>
              {["Conformité","Déontologie","CGU","Plan du site","Médiation Bancaire","Grille tarifaire","Réclamations"].map(l => (
                <a key={l} href="#" style={{ color: 'rgba(255,255,255,0.45)', fontSize: 11, textDecoration: 'none' }}>{l}</a>
              ))}
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px 24px' }}>
              {["Protection des données personnelles","Informations Réglementaires","Paramètres des cookies"].map(l => (
                <a key={l} href="#" style={{ color: 'rgba(255,255,255,0.45)', fontSize: 11, textDecoration: 'none' }}>{l}</a>
              ))}
            </div>
          </div>

          <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', padding: '14px 60px', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, color: 'rgba(255,255,255,0.35)', fontSize: 11 }}>
            <span>Conception et développement : <strong style={{ color: '#FFF' }}>VOID</strong></span>
            <span>Tous droits réservés</span>
          </div>
        </footer>
      </div>

      <style>{`a:hover { color: #F26522 !important; }`}</style>
    </div>
  );
};

export default HomePage;