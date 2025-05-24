import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn, UpdateDateColumn, ManyToOne, JoinColumn } from 'typeorm';
import { User } from '../../user/entities/user.entity';

export enum ChainType {
  EVM = 'EVM',
  SOLANA = 'SOLANA',
  MOVE = 'MOVE',
  COSMOS = 'COSMOS',
  CAIRO = 'CAIRO'
}

export enum Platform {
  TELEGRAM = 'TELEGRAM',
  DISCORD = 'DISCORD',
  WEB = 'WEB'
}

@Entity('wallets')
export class Wallet {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'uuid' })
  userId: string;

  @ManyToOne(() => User)
  @JoinColumn({ name: 'userId' })
  user: User;

  @Column({ type: 'enum', enum: Platform })
  platform: Platform;

  @Column({ type: 'enum', enum: ChainType })
  chainType: ChainType;

  @Column()
  chainId: number;

  @Column()
  address: string;

  @Column()
  encryptedPrivateKey: string;

  @Column({ nullable: true })
  encryptedMnemonic: string;

  @Column({ default: true })
  isActive: boolean;

  @CreateDateColumn()
  createdAt: Date;

  @UpdateDateColumn()
  updatedAt: Date;
} 