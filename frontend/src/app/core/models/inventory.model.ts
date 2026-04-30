export interface InventoryItem {
  nro_lpn: string;
  estado: string;
  producto: string;
  descripcion: string;
  curva: string;
}

export interface ProcessingJob {
  job_id: string;
  filename: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  total_rows: number;
  processed_rows: number;
  progress_pct: number;
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

export interface UploadInitiated {
  job_id: string;
  message: string;
}

export type EstadoType = 'Ubicado' | 'Parcialmente asignado' | 'Asignado' | string;
export type CurvaType = 'A' | 'B' | 'C' | '0' | string;
