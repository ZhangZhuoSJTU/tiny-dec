static int bump(int x) {
    return x + 3;
}

static int mix(int left, int right) {
    if (left < right) {
        return bump(left + right);
    }
    return bump(left - right);
}

static int fold(int limit, int seed) {
    int total = seed;
    for (int i = 0; i < limit; i++) {
        int next = mix(total, i + seed);
        if (next < 15) {
            total = total + next;
        } else {
            total = total - i;
        }
    }
    return total;
}

int main(void) {
    return fold(5, 2);
}
