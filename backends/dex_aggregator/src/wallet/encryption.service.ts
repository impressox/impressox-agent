import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as CryptoJS from 'crypto-js';
import * as crypto from 'crypto';

@Injectable()
export class EncryptionService {
  private readonly encryptionKey: string;

  constructor(private configService: ConfigService) {
    this.encryptionKey = this.configService.get<string>('ENCRYPTION_KEY');
    if (!this.encryptionKey) {
      throw new Error('ENCRYPTION_KEY is not defined');
    }
  }

  /**
   * Generate a secure encryption key
   * @returns A secure random string suitable for use as an encryption key
   */
  static generateEncryptionKey(): string {
    // Generate 32 random bytes
    const randomBytes = crypto.randomBytes(32);
    // Convert to base64 string
    return randomBytes.toString('base64');
  }

  encrypt(text: string): string {
    return CryptoJS.AES.encrypt(text, this.encryptionKey).toString();
  }

  decrypt(encryptedText: string): string {
    const bytes = CryptoJS.AES.decrypt(encryptedText, this.encryptionKey);
    return bytes.toString(CryptoJS.enc.Utf8);
  }

  generateUserSecret(): string {
    return CryptoJS.lib.WordArray.random(16).toString();
  }
} 