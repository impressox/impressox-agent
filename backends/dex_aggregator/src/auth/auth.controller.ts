import { Controller, Post, Body } from '@nestjs/common';
import { AuthService } from './auth.service';
import { 
  LoginDto, 
  RegisterDto, 
  TelegramAuthDto,
  Web3AuthDto,
  GoogleAuthDto
} from './auth.dto';

@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post('login')
  async login(@Body() credentials: LoginDto) {
    return this.authService.login(credentials);
  }

  @Post('register')
  async register(@Body() userData: RegisterDto) {
    return this.authService.register(userData);
  }

  @Post('telegram')
  async telegramAuth(@Body() data: TelegramAuthDto) {
    return this.authService.telegramAuth(data);
  }

  @Post('web3')
  async web3Auth(@Body() data: Web3AuthDto) {
    return this.authService.web3Auth(data);
  }

  @Post('google')
  async googleAuth(@Body() data: GoogleAuthDto) {
    return this.authService.googleAuth(data);
  }
} 