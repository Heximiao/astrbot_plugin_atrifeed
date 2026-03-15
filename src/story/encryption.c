#include <stdio.h>
#include <string.h>

// 密钥，需要和 Python 端保持一致
const char* SECRET_KEY = "ATRI_MY_DEAR_MOMENTS"; 

void encrypt_decrypt(FILE *input, FILE *output) {
    int ch;
    int i = 0;
    int key_len = strlen(SECRET_KEY);
    
    while ((ch = fgetc(input)) != EOF) {
        // 核心逻辑：字节异或
        fputc(ch ^ SECRET_KEY[i % key_len], output);
        i++;
    }
}

int main() {
    FILE *in = fopen("main_pilgrimage.yaml", "rb");
    FILE *out = fopen("main_pilgrimage.dat", "wb");
    
    if (in == NULL || out == NULL) {
        printf("文件打开失败！\n");
        return 1;
    }

    encrypt_decrypt(in, out);
    
    fclose(in);
    fclose(out);
    printf("加密完成，生成 main_pilgrimage.dat\n");
    return 0;
}