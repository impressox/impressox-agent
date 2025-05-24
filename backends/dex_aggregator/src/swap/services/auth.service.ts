import { Injectable, Logger, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { JwtService } from '@nestjs/jwt';
import { User } from '../../auth/entities/user.entity';
import { WalletService } from '../../wallet/wallet.service';

@Injectable()
export class AuthService {
  private readonly logger = new Logger(AuthService.name);

  constructor(
    private readonly configService: ConfigService,
    private readonly jwtService: JwtService,
    private readonly walletService: WalletService,
  ) {}

  async getUserPrivateKey(walletAddress: string): Promise<string> {
    try {
      // Get user from wallet address
      const user = await this.walletService.getUserByWalletAddress(walletAddress);
      if (!user) {
        throw new UnauthorizedException('User not found');
      }

      // Get wallet from user
      const wallet = await this.walletService.getWalletByAddress(walletAddress);
      if (!wallet) {
        throw new UnauthorizedException('Wallet not found');
      }

      // Return decrypted private key
      return this.walletService.getDecryptedPrivateKey(wallet.id, wallet.userId);
    } catch (error) {
      this.logger.error(`Error getting user private key: ${error.message}`);
      throw new UnauthorizedException('Failed to get user private key');
    }
  }

  async validateUser(userId: string): Promise<User> {
    try {
      const user = await this.walletService.getUserById(userId);
      if (!user) {
        throw new UnauthorizedException('User not found');
      }
      return user;
    } catch (error) {
      this.logger.error(`Error validating user: ${error.message}`);
      throw new UnauthorizedException('Failed to validate user');
    }
  }
} 