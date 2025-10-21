import { useEffect, useState } from "react";
import axios from "axios";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [message, setMessage] = useState("");
  const [endpoints, setEndpoints] = useState([]);

  // Auth
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [result, setResult] = useState("");

  // Upload
  const [recto, setRecto] = useState(null);
  const [verso, setVerso] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);
  const [suggestions, setSuggestions] = useState([]);

  // Confirm
  const [confirmData, setConfirmData] = useState({
    name: "",
    set_name: "",
    number: "",
    rarity: "",
    price: "",
    image: "",
    finish: "Normal"
  });
  const [confirmResult, setConfirmResult] = useState("");

  // Charger message d'accueil
  useEffect(() => {
    axios.get(API_URL + "/")
      .then(res => {
        setMessage(res.data.message);
        setEndpoints(res.data.endpoints || []);
      })
      .catch(() => setMessage("❌ Impossible de se connecter à l'API"));
  }, []);

  // Register
  const register = async () => {
    try {
      const formData = new FormData();
      formData.append("email", email);
      formData.append("password", password);

      const res = await axios.post(API_URL + "/register", formData);
      setResult(res.data.message);
    } catch (err) {
      setResult("Erreur : " + (err.response?.data?.detail || err.message));
    }
  };

  // Login
  const login = async () => {
    try {
      const formData = new FormData();
      formData.append("username", email);
      formData.append("password", password);

      const res = await axios.post(API_URL + "/token", formData);
      setToken(res.data.access_token);
      setResult("✅ Connecté avec succès !");
    } catch (err) {
      setResult("Erreur login : " + (err.response?.data?.detail || err.message));
    }
  };

  // Upload
  const uploadCard = async () => {
    if (!token) {
      setUploadResult("⚠️ Vous devez être connecté avant d'uploader");
      return;
    }
    if (!recto || !verso) {
      setUploadResult("❌ Merci de sélectionner recto et verso");
      return;
    }
    try {
      const formData = new FormData();
      formData.append("recto", recto);
      formData.append("verso", verso);

      const res = await axios.post(API_URL + "/upload", formData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUploadResult(res.data);
      setSuggestions(res.data.suggestions || []);
    } catch (err) {
      setUploadResult("Erreur upload : " + (err.response?.data?.detail || err.message));
    }
  };

  // Choisir une suggestion
  const chooseSuggestion = (s) => {
    setConfirmData({
      name: s.name || "",
      set_name: s.set || "",
      number: s.number || "",
      rarity: s.rarity || "",
      price: s.prices?.averageSellPrice || 0,
      image: s.image || "",
      finish: "Normal"
    });
  };

  // Confirm
  const confirmCard = async () => {
    try {
      const formData = new FormData();
      Object.entries(confirmData).forEach(([key, value]) => {
        formData.append(key, value);
      });

      const res = await axios.post(API_URL + "/confirm", formData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setConfirmResult(res.data.message);
    } catch (err) {
      setConfirmResult("Erreur confirm : " + (err.response?.data?.detail || err.message));
    }
  };

  return (
    <div style={{ fontFamily: "Arial", padding: "20px" }}>
      <h1>PokéCollection ⚡</h1>
      <h2>{message}</h2>

      <h3>Endpoints disponibles :</h3>
      <ul>
        {endpoints.map((ep, i) => (
          <li key={i}>{ep}</li>
        ))}
      </ul>

      <h3>Authentification</h3>
      <input
        placeholder="Email"
        value={email}
        onChange={e => setEmail(e.target.value)}
      />
      <input
        type="password"
        placeholder="Mot de passe"
        value={password}
        onChange={e => setPassword(e.target.value)}
      />
      <div style={{ marginTop: "10px" }}>
        <button onClick={register}>Créer un compte</button>
        <button onClick={login}>Se connecter</button>
      </div>

      {token && (
        <div style={{ marginTop: "20px" }}>
          <p>🔑 Token stocké : {token.substring(0, 20)}...</p>

          <h3>Upload d'une carte</h3>
          <input type="file" onChange={e => setRecto(e.target.files[0])} />
          <input type="file" onChange={e => setVerso(e.target.files[0])} />
          <button onClick={uploadCard}>Uploader</button>

          {uploadResult && (
            <pre style={{ background: "#eee", padding: "10px", marginTop: "10px" }}>
              {JSON.stringify(uploadResult, null, 2)}
            </pre>
          )}

          {suggestions.length > 0 && (
            <div style={{ marginTop: "20px" }}>
              <h3>Suggestions trouvées :</h3>
              <ul>
                {suggestions.map((s, i) => (
                  <li key={i} style={{ marginBottom: "10px" }}>
                    <img src={s.image} alt={s.name} style={{ height: "80px" }} />
                    <div>
                      <strong>{s.name}</strong> ({s.set}) #{s.number}  
                      <br />Rareté : {s.rarity || "?"}
                      <br />Prix moyen : {s.prices?.averageSellPrice || "?"} €
                    </div>
                    <button onClick={() => chooseSuggestion(s)}>Choisir</button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {confirmData.name && (
            <div style={{ marginTop: "20px" }}>
              <h3>Confirmer la carte</h3>
              <input
                placeholder="Nom"
                value={confirmData.name}
                onChange={e => setConfirmData({ ...confirmData, name: e.target.value })}
              />
              <input
                placeholder="Set"
                value={confirmData.set_name}
                onChange={e => setConfirmData({ ...confirmData, set_name: e.target.value })}
              />
              <input
                placeholder="Numéro"
                value={confirmData.number}
                onChange={e => setConfirmData({ ...confirmData, number: e.target.value })}
              />
              <input
                placeholder="Rareté"
                value={confirmData.rarity}
                onChange={e => setConfirmData({ ...confirmData, rarity: e.target.value })}
              />
              <input
                placeholder="Prix"
                type="number"
                value={confirmData.price}
                onChange={e => setConfirmData({ ...confirmData, price: e.target.value })}
              />
              <input
                placeholder="Image URL"
                value={confirmData.image}
                onChange={e => setConfirmData({ ...confirmData, image: e.target.value })}
              />

              {/* Nouveau champ finish */}
              <select
                value={confirmData.finish}
                onChange={e => setConfirmData({ ...confirmData, finish: e.target.value })}
              >
                <option value="Normal">Normal</option>
                <option value="Holo">Holo</option>
                <option value="Reverse">Reverse</option>
              </select>

              <button onClick={confirmCard}>Confirmer</button>

              {confirmResult && (
                <p style={{ color: "green", marginTop: "10px" }}>{confirmResult}</p>
              )}
            </div>
          )}
        </div>
      )}

      <p style={{ marginTop: "20px", color: "blue" }}>{result}</p>
    </div>
  );
}

export default App;