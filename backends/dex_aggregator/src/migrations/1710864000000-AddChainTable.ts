import { MigrationInterface, QueryRunner } from 'typeorm';

export class AddChainTable1710864000000 implements MigrationInterface {
  public async up(queryRunner: QueryRunner): Promise<void> {
    // Create chain table
    await queryRunner.query(`
      CREATE TABLE "chains" (
        "id" SERIAL PRIMARY KEY,
        "chain_id" integer NOT NULL,
        "name" varchar NOT NULL,
        "is_active" boolean NOT NULL DEFAULT true,
        "created_at" TIMESTAMP NOT NULL DEFAULT now(),
        "updated_at" TIMESTAMP NOT NULL DEFAULT now()
      )
    `);

    // Add unique constraint for chain_id
    await queryRunner.query(`
      ALTER TABLE "chains" ADD CONSTRAINT "UQ_chains_chain_id" UNIQUE ("chain_id")
    `);

    // Add chain_id column to chain_providers table
    await queryRunner.query(`
      ALTER TABLE "chain_providers" ADD COLUMN "chain_id" integer
    `);

    // Add foreign key constraint
    await queryRunner.query(`
      ALTER TABLE "chain_providers" 
      ADD CONSTRAINT "FK_chain_providers_chains" 
      FOREIGN KEY ("chain_id") REFERENCES "chains"("id") 
      ON DELETE CASCADE
    `);

    // Migrate existing data
    await queryRunner.query(`
      INSERT INTO "chains" (chain_id, name, is_active)
      SELECT DISTINCT chain_id, 
        CASE 
          WHEN chain_type = 'ethereum' THEN 'Ethereum'
          WHEN chain_type = 'bsc' THEN 'BNB Chain'
          WHEN chain_type = 'polygon' THEN 'Polygon'
          WHEN chain_type = 'arbitrum' THEN 'Arbitrum'
          WHEN chain_type = 'optimism' THEN 'Optimism'
          ELSE chain_type
        END,
        true
      FROM chain_providers
      WHERE chain_id IS NOT NULL
    `);

    // Update chain_providers table to reference chains table
    await queryRunner.query(`
      UPDATE chain_providers cp
      SET chain_id = c.id
      FROM chains c
      WHERE cp.chain_id = c.chain_id
    `);

    // Make chain_id not null after data migration
    await queryRunner.query(`
      ALTER TABLE "chain_providers" ALTER COLUMN "chain_id" SET NOT NULL
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    // Drop foreign key constraint
    await queryRunner.query(`
      ALTER TABLE "chain_providers" DROP CONSTRAINT "FK_chain_providers_chains"
    `);

    // Drop chain_id column
    await queryRunner.query(`
      ALTER TABLE "chain_providers" DROP COLUMN "chain_id"
    `);

    // Drop chains table
    await queryRunner.query(`
      DROP TABLE "chains"
    `);
  }
} 