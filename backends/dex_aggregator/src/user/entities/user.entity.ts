import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn, UpdateDateColumn, OneToMany } from 'typeorm';
import { Platform } from '../../wallet/entities/wallet.entity';
import { AuthMethod } from '../../auth/auth.dto';
import { Wallet } from '../../wallet/entities/wallet.entity';

@Entity('users')
export class User {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ nullable: true })
  name: string;

  @Column({ nullable: true, unique: true })
  email: string;

  @Column({ nullable: true })
  password: string;

  @Column({ type: 'enum', enum: Platform, default: Platform.WEB })
  platform: Platform;

  @Column({ type: 'enum', enum: AuthMethod, nullable: true })
  authMethod: AuthMethod;

  @Column({ nullable: true })
  clientId: string;

  @Column({ nullable: true })
  telegramId: string;

  @Column({ nullable: true })
  discordId: string;

  @Column({ nullable: true })
  googleId: string;

  @Column({ nullable: true })
  walletAddress: string;

  @Column({ default: true })
  isActive: boolean;

  @OneToMany(() => Wallet, wallet => wallet.user)
  wallets: Wallet[];

  @CreateDateColumn()
  createdAt: Date;

  @UpdateDateColumn()
  updatedAt: Date;
} 