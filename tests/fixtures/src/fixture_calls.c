typedef __SIZE_TYPE__ size_t;

extern void *malloc(size_t size);
extern void free(void *ptr);
extern int puts(const char *s);
extern void *memset(void *s, int c, size_t n);

int main(void) {
    char *buffer = (char *)malloc(32);
    if (buffer == 0) {
        return 1;
    }

    memset(buffer, 0, 32);
    puts("tiny_dec fixture");
    free(buffer);
    return 0;
}
