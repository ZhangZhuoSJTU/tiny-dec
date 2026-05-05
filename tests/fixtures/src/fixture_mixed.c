typedef struct {
    int opcode;
    int amount;
} Step;

static int adjust_step(Step *step, int total) {
    switch (step->opcode) {
        case 0:
            return total + step->amount;
        case 1:
            return total - step->amount;
        case 2:
            return total + (step->amount << 1);
        case 3:
            return total + (step->amount + 7);
        default:
            return total + (step->amount - 1);
    }
}

static int run_steps(Step *steps, int count, int seed) {
    int total = seed;
    for (int i = 0; i < count; i++) {
        int adjusted = adjust_step(&steps[i], total);
        if (adjusted < 20) {
            total = total + adjusted;
        } else {
            total = total - steps[i].opcode;
        }
    }
    return total;
}

int main(void) {
    Step steps[4] = {
        {0, 3},
        {2, 4},
        {1, 5},
        {3, 2},
    };
    return run_steps(steps, 4, 6);
}
