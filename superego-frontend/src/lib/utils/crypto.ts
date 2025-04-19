/**
 * Utility functions for encrypting API keys
 * Uses CryptoJS AES encryption with a fixed key
 */

// Import the necessary crypto libraries
import CryptoJS from 'crypto-js';

// Fixed encryption key - must match the backend
const SECRET_KEY = 'superego-encryption-key-28jgowgnwvnwoqb';

/**
 * Encrypts an API key using CryptoJS AES encryption
 * @param apiKey The API key to encrypt
 * @returns The encrypted API key as a Base64 string
 */
export function encryptApiKey(apiKey: string): string {
  console.log('[crypto.ts] Encrypting API key, length:', apiKey ? apiKey.length : 0);
  if (!apiKey) {
    console.log('[crypto.ts] Empty API key, returning empty string');
    return '';
  }
  
  try {
    // Use CryptoJS AES encryption with the secret key
    // This will include the IV and salt in the output format
    // The backend expects this format
    const encrypted = CryptoJS.AES.encrypt(apiKey, SECRET_KEY);
    
    // Convert to string (this is the format the backend expects)
    const encryptedString = encrypted.toString();
    
    console.log('[crypto.ts] Encryption successful, result length:', encryptedString.length);
    console.log('[crypto.ts] Encrypted format:', encryptedString.substring(0, 20) + '...');
    
    return encryptedString;
  } catch (error) {
    console.error('[crypto.ts] Error encrypting API key:', error);
    return '';
  }
}

/**
 * Generates a random session ID
 * @returns A random session ID
 */
export function generateSessionId(): string {
  // Generate a random string of 16 characters
  const randomBytes = CryptoJS.lib.WordArray.random(8);
  return randomBytes.toString(CryptoJS.enc.Hex);
}

/**
 * Gets the current session ID from localStorage or generates a new one
 * @returns The current session ID
 */
export function getOrCreateSessionId(): string {
  const storageKey = 'superego-session-id';
  let sessionId = localStorage.getItem(storageKey);
  
  if (!sessionId) {
    sessionId = generateSessionId();
    localStorage.setItem(storageKey, sessionId);
    console.log('[crypto.ts] Created new session ID:', sessionId);
  } else {
    console.log('[crypto.ts] Using existing session ID:', sessionId);
  }
  
  return sessionId;
}
