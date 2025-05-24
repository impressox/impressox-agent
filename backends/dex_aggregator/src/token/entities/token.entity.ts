import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn, UpdateDateColumn } from 'typeorm';
import { ChainType } from '../../wallet/entities/wallet.entity';

@Entity('tokens')
export class Token {
  @PrimaryGeneratedColumn()
  id: number;

  @Column()
  address: string;

  @Column()
  symbol: string;

  @Column()
  name: string;

  @Column()
  decimals: number;

  @Column({
    type: 'enum',
    enum: ChainType
  })
  chainType: ChainType;

  @Column()
  chainId: number;

  @Column({ type: 'decimal', precision: 10, scale: 4, default: 0.5 })
  fee: number; // Fee in percentage (0.5 = 0.5%)

  @Column({ nullable: true })
  auditStatus: string;

  @Column({ nullable: true })
  auditReport: string;

  @Column({ nullable: true })
  auditDate: Date;

  @Column({ nullable: true })
  contractVerified: boolean;

  @Column({ nullable: true })
  contractSource: string;

  @Column({ default: true })
  isActive: boolean;

  @CreateDateColumn()
  createdAt: Date;

  @UpdateDateColumn()
  updatedAt: Date;
} 