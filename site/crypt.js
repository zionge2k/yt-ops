// Decrypts the data.enc envelope produced by ytops/crypt.py (PBKDF2-SHA256 + AES-256-GCM).
function b64ToBytes(b64) {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function decryptEnvelope(envelopeObj, password) {
  const enc = new TextEncoder();
  const baseKey = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"]);
  const key = await crypto.subtle.deriveKey(
    { name: "PBKDF2", hash: "SHA-256", salt: b64ToBytes(envelopeObj.salt), iterations: envelopeObj.iter },
    baseKey,
    { name: "AES-GCM", length: 256 },
    false,
    ["decrypt"]
  );
  const plain = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: b64ToBytes(envelopeObj.iv) },
    key,
    b64ToBytes(envelopeObj.ct)
  );
  return new TextDecoder().decode(plain);
}
