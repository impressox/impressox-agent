import { Injectable, UnauthorizedException, Logger } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import { 
  LoginDto, 
  RegisterDto, 
  JwtPayload, 
  TelegramAuthDto,
  Web3AuthDto,
  GoogleAuthDto,
} from './auth.dto';
import { User } from '../user/entities/user.entity';
import { UserService } from '../user/user.service';
import { WalletService } from '../wallet/wallet.service';
import { ChainType } from '../wallet/entities/wallet.entity';

@Injectable()
export class AuthService {
  private readonly logger = new Logger(AuthService.name);

  constructor(
    private readonly jwtService: JwtService,
    private readonly userService: UserService,
    private readonly walletService: WalletService,
    private readonly configService: ConfigService,
  ) {}

  private async ensureWalletExists(userId: string) {
    try {
      const wallets = await this.walletService.getWallets(userId);
      if (wallets.length === 0) {
        const user = await this.userService.findById(userId);
        // Create default EVM wallet for mainnet
        await this.walletService.createWallet(userId, ChainType.EVM, 1);
        // Create default Solana wallet
        await this.walletService.createWallet(userId, ChainType.SOLANA, 1);
      }
    } catch (error) {
      this.logger.error('Error ensuring wallet exists:', error);
    }
  }

  private generateToken(user: User) {
    const payload: JwtPayload = { 
      sub: user.id,
      email: user.email,
      platform: user.platform,
      authMethod: user.authMethod 
    };
    return this.jwtService.sign(payload);
  }

  async login(credentials: LoginDto) {
    const user = await this.userService.validateUser(credentials.email, credentials.password);
    await this.ensureWalletExists(user.id);
    return {
      access_token: this.generateToken(user),
      user
    };
  }

  async register(userData: RegisterDto) {
    const user = await this.userService.create(userData);
    await this.ensureWalletExists(user.id);
    return {
      access_token: this.generateToken(user),
      user
    };
  }

  async telegramAuth(data: TelegramAuthDto) {
    const user = await this.userService.findOrCreateByTelegram(data);
    await this.ensureWalletExists(user.id);
    return {
      access_token: this.generateToken(user),
      user
    };
  }

  async web3Auth(data: Web3AuthDto) {
    const user = await this.userService.findOrCreateByWeb3(data);
    await this.ensureWalletExists(user.id);
    return {
      access_token: this.generateToken(user),
      user
    };
  }

  async googleAuth(data: GoogleAuthDto) {
    const user = await this.userService.findOrCreateByGoogle(data);
    await this.ensureWalletExists(user.id);
    return {
      access_token: this.generateToken(user),
      user
    };
  }

  async validateUser(payload: JwtPayload): Promise<User> {
    const user = await this.userService.findById(payload.sub);
    if (!user) {
      throw new UnauthorizedException('User not found');
    }
    return user;
  }

  async getUserPrivateKey(walletAddress: string): Promise<string> {
    try {
      const wallet = await this.walletService.getWalletByAddress(walletAddress);
      if (!wallet) {
        throw new UnauthorizedException('Wallet not found');
      }
      return this.walletService.getDecryptedPrivateKey(wallet.id, wallet.userId);
    } catch (error) {
      this.logger.error(`Error getting user private key: ${error.message}`);
      throw new UnauthorizedException('Failed to get user private key');
    }
  }
} 