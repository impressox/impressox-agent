import { Entity, Column, PrimaryGeneratedColumn, CreateDateColumn, UpdateDateColumn, ManyToOne, JoinColumn } from 'typeorm';
import { ChainType } from '../../wallet/entities/wallet.entity';
import { DexProvider } from './provider.enum';
import { Chain } from './chain.entity';

@Entity('chain_providers')
export class ChainProvider {
  @PrimaryGeneratedColumn()
  id: number;

  @ManyToOne(() => Chain)
  @JoinColumn({ name: 'chain_id' })
  chain: Chain;

  @Column({ name: 'chain_id' })
  chainId: number;

  @Column({
    type: 'enum',
    enum: ChainType,
    name: 'chain_type'
  })
  chainType: ChainType;

  @Column({
    type: 'enum',
    enum: DexProvider
  })
  provider: DexProvider;

  @Column({ name: 'api_url' })
  apiUrl: string;

  @Column({ type: 'jsonb', nullable: true })
  config: Record<string, any>;

  @Column({ name: 'is_active', default: true })
  isActive: boolean;

  @Column({ type: 'decimal', precision: 10, scale: 4, default: 0 })
  priority: number; // Higher number means higher priority

  @Column({ name: 'rpc_url' })
  rpcUrl: string;

  @Column({ name: 'router_address', nullable: true })
  routerAddress: string;

  @Column({ type: 'jsonb', name: 'router_abi', nullable: true })
  routerAbi: any[];

  @CreateDateColumn({ name: 'created_at' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at' })
  updatedAt: Date;
} 