typedef int (*BinaryOp)(int, int);

static int add_pair(int left, int right) {
    return left + right;
}

static int blend_pair(int left, int right) {
    return (left ^ right) - 3;
}

__attribute__((noinline))
static BinaryOp choose_op(volatile int *selector) {
    if ((*selector & 1) == 0) {
        return add_pair;
    }
    return blend_pair;
}

int main(void) {
    volatile int selector = 5;
    BinaryOp op = choose_op(&selector);
    return op(selector + 2, 9);
}
