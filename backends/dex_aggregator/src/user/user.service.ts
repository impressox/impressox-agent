import { Injectable, NotFoundException, UnauthorizedException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { User } from './entities/user.entity';
import { GoogleAuthDto, Web3AuthDto, TelegramAuthDto, AuthMethod } from '../auth/auth.dto';
import * as bcrypt from 'bcrypt';
import { Platform } from '../wallet/entities/wallet.entity';

@Injectable()
export class UserService {
  constructor(
    @InjectRepository(User)
    private readonly userRepository: Repository<User>,
  ) {}

  async create(userData: Partial<User>): Promise<User> {
    const user = this.userRepository.create(userData);
    return this.userRepository.save(user);
  }

  async findById(id: string): Promise<User> {
    const user = await this.userRepository.findOne({ where: { id } });
    if (!user) {
      throw new NotFoundException('User not found');
    }
    return user;
  }

  async findByEmail(email: string): Promise<User | null> {
    return this.userRepository.findOne({ where: { email } });
  }

  async findByTelegramId(telegramId: string): Promise<User | null> {
    return this.userRepository.findOne({ where: { telegramId } });
  }

  async findByDiscordId(discordId: string): Promise<User | null> {
    return this.userRepository.findOne({ where: { discordId } });
  }

  async findByGoogleId(googleId: string): Promise<User | null> {
    return this.userRepository.findOne({ where: { googleId } });
  }

  async findByWalletAddress(walletAddress: string): Promise<User | null> {
    return this.userRepository.findOne({ where: { walletAddress } });
  }

  async findByClientId(platform: Platform, clientId: string): Promise<User | null> {
    return this.userRepository.findOne({ 
      where: { 
        platform,
        clientId 
      } 
    });
  }

  async findOrCreateByClientId(platform: Platform, clientId: string, name: string, email?: string): Promise<{ user: User; isNewUser: boolean }> {
    let user = await this.findByClientId(platform, clientId);
    let isNewUser = false;

    if (!user) {
      if (email) {
        user = await this.findByEmail(email);
      }

      if (!user) {
        user = await this.create({
          platform,
          clientId,
          name,
          email
        });
        isNewUser = true;
      } else {
        user = await this.update(user.id, {
          platform,
          clientId
        });
      }
    }

    return { user, isNewUser };
  }

  async update(id: string, data: Partial<User>): Promise<User> {
    await this.userRepository.update(id, data);
    return this.findById(id);
  }

  async delete(id: string): Promise<void> {
    const result = await this.userRepository.delete(id);
    if (result.affected === 0) {
      throw new NotFoundException('User not found');
    }
  }

  async validateUser(email: string, password: string): Promise<User> {
    const user = await this.findByEmail(email);
    if (!user) {
      throw new UnauthorizedException('Invalid credentials');
    }

    const isPasswordValid = await bcrypt.compare(password, user.password);
    if (!isPasswordValid) {
      throw new UnauthorizedException('Invalid credentials');
    }

    return user;
  }

  async findOrCreateByGoogle(data: GoogleAuthDto): Promise<User> {
    let user = await this.findByGoogleId(data.googleId);
    
    if (!user) {
      user = await this.findByEmail(data.email);
      
      if (!user) {
        user = await this.create({
          name: data.name,
          email: data.email,
          platform: Platform.WEB,
          authMethod: AuthMethod.GOOGLE,
          googleId: data.googleId,
        });
      } else {
        user = await this.update(user.id, {
          platform: Platform.WEB,
          authMethod: AuthMethod.GOOGLE,
          googleId: data.googleId,
        });
      }
    }
    
    return user;
  }

  async findOrCreateByWeb3(data: Web3AuthDto): Promise<User> {
    let user = await this.findByWalletAddress(data.walletAddress);
    
    if (!user) {
      if (data.email) {
        user = await this.findByEmail(data.email);
      }
      
      if (!user) {
        user = await this.create({
          name: data.name,
          email: data.email,
          platform: Platform.WEB,
          authMethod: AuthMethod.WEB3,
          walletAddress: data.walletAddress,
        });
      } else {
        user = await this.update(user.id, {
          platform: Platform.WEB,
          authMethod: AuthMethod.WEB3,
          walletAddress: data.walletAddress,
        });
      }
    }
    
    return user;
  }

  async findOrCreateByTelegram(data: TelegramAuthDto): Promise<User> {
    let user = await this.findByTelegramId(data.telegramId);
    
    if (!user) {
      if (data.email) {
        user = await this.findByEmail(data.email);
      }
      
      if (!user) {
        user = await this.create({
          name: data.name,
          email: data.email,
          platform: Platform.TELEGRAM,
          authMethod: AuthMethod.TELEGRAM,
          telegramId: data.telegramId,
        });
      } else {
        user = await this.update(user.id, {
          platform: Platform.TELEGRAM,
          authMethod: AuthMethod.TELEGRAM,
          telegramId: data.telegramId,
        });
      }
    }
    
    return user;
  }
} 